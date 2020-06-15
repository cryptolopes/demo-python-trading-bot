import pywaves as pw
import datetime
from time import sleep
import os
import configparser

# some property will be superseded by the config file
class SimpleBot:
    def __init__(self):
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        s = format(timestamp)
        self.log_file = "bot_" + s + ".log" 
        self.node = "https://nodes.wavesnodes.com"
        self.chain = "mainnet"
        self.matcher = "https://matcher.waves.exchange"
        self.order_fee = int(0.003 * 10 ** 8)
        self.order_lifetime = 29 * 86400  # 29 days
        self.private_key = ""
        self.amount_asset = pw.WAVES
        self.price_asset_id = "8LQW8f7P5d5PZM7GtZEBgaqRPGSzS3DfPuiXrURJ4AJS" # BTC
        self.price_asset = pw.Asset(self.price_asset_id)  
        self.price_step = 0.005
        self.min_amount = 10000 #satoshi
        self.seconds_to_sleep = 40
        self.price_asset_name = "BTC"

    def log(self, msg):
        timestamp = datetime.datetime.utcnow().strftime("%b %d %Y %H:%M:%S UTC")
        s = "[{0}]:{1}".format(timestamp, msg)
        print(s)
        try:
            f = open(self.log_file, "a")
            f.write(s + "\n")
            f.close()
        except OSError:
            pass

    def read_config(self, cfg_file):
        if not os.path.isfile(cfg_file):
            self.log("Missing config file")
            self.log("Exiting.")
            exit(1)

        try:
            self.log("Reading config file '{0}'".format(cfg_file))
            config = configparser.RawConfigParser()
            config.read(cfg_file)
            self.node = config.get('main', 'node')
            self.chain = config.get('main', 'network')
            self.matcher = config.get('main', 'matcher')
            self.order_fee = config.getint('main', 'order_fee')
            self.order_lifetime = config.getint('main', 'order_lifetime')

            self.private_key = config.get('account', 'private_key')
            self.amount_asset_id = config.get('market', 'amount_asset')
            self.amount_asset = pw.Asset(self.amount_asset_id)
            self.price_asset_id = config.get('market', 'price_asset')
            self.price_asset = pw.Asset(self.price_asset_id)
            self.price_step = config.getfloat('market', 'price_step')
            self.price_asset_name = config.get('market','price_asset_name')
        except OSError:
            self.log("Error reading config file")
            self.log("Exiting.")
            exit(1)

    
def main():
    bot = SimpleBot()
    bot.read_config("config.cfg")
    pw.setNode(node=bot.node, chain=bot.chain)
    pw.setMatcher(node=bot.matcher)
    my_address = pw.Address(privateKey=bot.private_key)

    bot.log("")
    bot.log("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    bot.log("+++++++++++++++++++   START NEW SESSION ++++++++++++++++++++++++")
    bot.log("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    bot.log("Price_asset_id        " + bot.price_asset_id )
    bot.log("Price_asset_name      " + bot.price_asset_name)
    bot.log("Price_asset.decimals  " + str(bot.price_asset.decimals))
    bot.log("Amount_asset.decimals " + str(bot.amount_asset.decimals))
    bot.log("Price_step            " + str(bot.price_step) + " " + bot.price_asset_name) 

    waves_btc = pw.AssetPair(bot.amount_asset, bot.price_asset)

    # ---- Calculate starting values
    start_waves_balance = my_address.balance()/(10 ** bot.amount_asset.decimals)
    start_btc_balance   = my_address.balance(bot.price_asset_id)/(10 ** bot.price_asset.decimals)

    order_book = waves_btc.orderbook()
    start_best_bid = order_book["bids"][0]["price"]/(10 ** bot.price_asset.decimals)
    start_best_ask = order_book["asks"][0]["price"]/(10 ** bot.price_asset.decimals)

    start_value = (start_waves_balance + (start_btc_balance/start_best_bid))

    bot.log("Starting best_bid = " + str(start_best_bid))
    bot.log("Starting best_ask = " + str(start_best_ask))
    bot.log("Starting WAVES balance = " + str(start_waves_balance))
    bot.log("Starting BTC   balance = " + str(start_btc_balance))
    bot.log("Starting Value         = " + str(start_value) + " Waves")

    bot.log("---------------------------------------------------------------")

    last_best_bid = start_best_bid
    last_best_ask = start_best_ask
        
    while True:
               
        # ---- collect balances
        waves_balance, btc_balance = my_address.tradableBalance(waves_btc)

        # ---- Collect last balances
        last_waves_balance = my_address.balance()/(10 ** bot.amount_asset.decimals)
        last_btc_balance   = my_address.balance(bot.price_asset_id)/(10 ** bot.price_asset.decimals)

        # ---- Collect last price
        order_book = waves_btc.orderbook()
        best_bid = order_book["bids"][0]["price"]/(10 ** bot.price_asset.decimals)
        best_ask = order_book["asks"][0]["price"]/(10 ** bot.price_asset.decimals)
        bot.log("Best_bid  = {0}, best_ask = {1}".format(best_bid, best_ask))

        bot.log("Last WAVES balance " + str(last_waves_balance))
        bot.log("Last BTC   balance " + str(last_btc_balance))
        bot.log("Last BID   Price   " + str(best_bid))

        # ---- calculate value and gain (respect actual price)
        value = (last_waves_balance + (last_btc_balance/best_bid))
        gain  = value - start_value
        bot.log("GAIN  = " + str(gain)  + " Waves")
        bot.log("VALUE = " + str(value) + " Waves")
        
        # ---- check if pool changed
        if ((best_bid == last_best_bid) and (best_ask == last_best_ask)):
            # Pool not changed
            # ----------------
            bot.log("Pool NOT changed")
        else:
            # pool changed
            # ------------

            # clear pending order
            my_address.cancelOpenOrders(waves_btc)
            sleep(2)

            # calculate what is better between sell or buy
            # it will sell waves (buying btc)  if btc price lower than previous price less spread
            # it will buy  waves (selling btc) if btc price greater than previous price plus spread

            # -------------------------------------------------
            ask_price= (best_ask + bot.price_step)
            bot.log("ask_price = " + str(ask_price))
            
            if (best_ask < ask_price):
                # buy waves selling btc
                # ---------------------                
                ask_amount = int( (last_btc_balance / ask_price)* 10 ** pw.WAVES.decimals) - (bot.order_fee *2)                
                bot.log("BUY price: {0}, ask amount:{1}".format(ask_price, ask_amount))
                last_best_ask = ask_price
                if ask_amount >= bot.min_amount:
                    bot.log("Post sell order")                
                    my_address.sell(assetPair=waves_btc, amount=ask_amount, price=ask_price, matcherFee=bot.order_fee, maxLifetime=bot.order_lifetime)
                    sleep(4)

                    # ---- collect balances
                    waves_balance, btc_balance = my_address.tradableBalance(waves_btc)

                    # ---- Collect last balances
                    last_waves_balance = my_address.balance()/(10 ** bot.amount_asset.decimals)
                    last_btc_balance   = my_address.balance(bot.price_asset_id)/(10 ** bot.price_asset.decimals)

                    
            # -------------------------------------------------
            bid_price = (best_bid - bot.price_step)
            bot.log("bid_price = " + str(bid_price))

            if (best_bid > bid_price):
                # sell waves buying btc
                # ---------------------
                bid_amount = int( (last_waves_balance * 10 ** bot.amount_asset.decimals)  - (bot.order_fee *2))                
                bot.log("SELL price: {0}, bid amount: {1}".format(bid_price, bid_amount))
                last_best_bid = bid_price
                if bid_amount >= bot.min_amount:
                    bot.log("Post buy order")
                    my_address.buy(assetPair=waves_btc, amount=bid_amount, price=bid_price, matcherFee=bot.order_fee, maxLifetime=bot.order_lifetime)



        bot.log("---------------------------------------------------------------")
        sleep(bot.seconds_to_sleep)


if __name__ == "__main__":
    main()

