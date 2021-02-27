#!/usr/bin/env python
# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord.ext import tasks
import json
import datetime
import requests

TOKEN = ""
PREFIX = ""
API_KEY = ""
ROLES = []

orders = []
feedback = []
stock_list = dict()

with open('config.json') as json_file:
    data = json.load(json_file)
    TOKEN = data["token"]
    PREFIX = data["prefix"]
    ROLES = data["permission_roles"]
    API_KEY = data["shoppy_api_key"]
    CUSTOMER_ROLE = data["customer_role"]


header = {
    'Authorization': API_KEY,
    'User-Agent': 'Shoppy-Bot'
}


client = commands.Bot(command_prefix=PREFIX)

client.remove_command("help")


@tasks.loop(seconds=60)
async def update():
    global stock_list
    with open('config.json') as json_file:
        data = json.load(json_file)
        restock_channel = data["restock_channel"]
    print("=> Updating...")
    products = get_products()
    for product in products:
        if product["id"] in stock_list:
            if stock_list[product["id"]] != int(product["stock"]):
                stock_list[product["id"]] = int(product["stock"])
                if int(product["stock"]) == 1:
                    embed = discord.Embed(title="Stock warning", description=product["title"] + " is low on stock", color=discord.Color.orange())
                    await client.get_channel(restock_channel).send(embed=embed)
                elif int(product["stock"]) == 0:
                    embed = discord.Embed(title="Empty Stock", description=product["title"] + " is empty on stock",
                                          color=discord.Color.red())
                    await client.get_channel(restock_channel).send(embed=embed)
                else:
                    embed = discord.Embed(title="Product restocked", description=product["title"] + " was restocked",
                                          color=discord.Color.blue())
                    if product["stock"] == 9223372036854775807:
                        stock = "Service"
                    else:
                        stock = str(product["stock"])
                    embed.add_field(name="Stock", value=stock)
                    await client.get_channel(restock_channel).send(embed=embed)
        else:
            stock_list[product["id"]] = int(product["stock"])
    print("=> Update finished ")


@client.command(name="help")
async def help(ctx):
    embed = discord.Embed(title="Help", description="See all Commands for "+client.user.name, color=discord.Color.blue())
    embed.add_field(name=PREFIX+"help", value="Displays the help", inline=False)
    embed.add_field(name=PREFIX+"stock", value="Displays the current stock", inline=False)
    embed.add_field(name=PREFIX+"verify <order_id>", value="Adds customer role to an user", inline=False)
    if has_permissions(ctx):
        embed.add_field(name=PREFIX+"checkorder <order_id>", value="Prints all information about an order", inline=False)
        embed.add_field(name=PREFIX+"replace <order_id> <amount>", value="Replace account from shoppy stock", inline=False)
    await ctx.send(embed=embed)


@client.command(name="verify")
async def verify(ctx, order_id):
    user = ctx.message.author
    order_information = get_order_information(order_id)
    if "status" in order_information and order_information["status"] is False:
        embed = discord.Embed(title="Order not found",
                              description="This order was not found",
                              color=discord.Color.red())
        await ctx.send(embed=embed)
        await ctx.message.delete()
        return
    if not order_information["paid_at"]:
        embed = discord.Embed(title="Order not confirmed",
                              description="This order is not confirmed yet. Please try again later",
                              color=discord.Color.orange())
        await ctx.send(embed=embed)
        await ctx.message.delete()
        return
    await user.add_roles(discord.utils.get(ctx.message.guild.roles, id=CUSTOMER_ROLE))
    embed = discord.Embed(title="Success", description="You should have received the customer role now!",
                          color=discord.Color.green())
    await ctx.send(embed=embed)
    await ctx.message.delete()


@client.command(name="checkorder")
async def checkorder(ctx, order_id):
    if not has_permissions(ctx):
        embed = discord.Embed(title="No permission",
                              description="You don't have the permissions to execute this command",
                              color=discord.Color.red())
        await ctx.send(embed=embed)
        return
    order_information = get_order_information(order_id)
    if "status" in order_information and order_information["status"] is False:
        embed = discord.Embed(title="Order not found",
                              description="This order was not found",
                              color=discord.Color.red())
        await ctx.send(embed=embed)
        return

    embed = discord.Embed(title="Order information", description="Order ID: "+order_information["id"], color=discord.Color.blue())
    embed.add_field(name="Email", value=order_information["email"], inline=False)
    embed.add_field(name="Product Name", value=order_information["product"]["title"], inline=False)
    embed.add_field(name="Confirmations", value=str(order_information["confirmations"]), inline=False)
    embed.add_field(name="Price", value=str(order_information["price"])+str(order_information["currency"]), inline=False)
    embed.add_field(name="Created at", value=order_information["created_at"], inline=False)
    embed.add_field(name="Gateway", value=order_information["gateway"], inline=False)
    embed.add_field(name="Quantity", value=order_information["quantity"], inline=False)
    if order_information["paid_at"]:
        embed.add_field(name="Paid at", value=order_information["paid_at"], inline=False)
    if order_information["transaction_id"]:
        embed.add_field(name="Transaction ID", value=order_information["transaction_id"], inline=False)
    if order_information["crypto_address"]:
        embed.add_field(name="Crypto Address", value=order_information["crypto_address"], inline=False)
    await ctx.send(embed=embed)

    embed = discord.Embed(title="Delivered Goods", description="Order ID: "+order_information["id"], color=discord.Color.blue())
    count = 0
    for account in order_information["accounts"]:
        if count % 25 == 0 and count / 25 != 0:
            await ctx.send(embed=embed)
            embed = discord.Embed(title="Delivered Goods", description="Page " + str(round(count / 25) + 1),
                                  color=discord.Color.blue())
        embed.add_field(name="`" + str(count) + "`", value=str(account["account"]), inline=False)
        count = count + 1
    await ctx.send(embed=embed)


@client.command(name="stock")
async def stock(ctx):
    embed = discord.Embed(title="Stock", color=discord.Color.blue())
    count = 0
    for product in get_products():
        if count % 25 == 0 and count / 25 != 0:
            await ctx.send(embed=embed)
            embed = discord.Embed(title="Stock", description="Page " + str(round(count / 25) + 1),
                                  color=discord.Color.green())
        if product["stock"] == 9223372036854775807:
            stock = "Service"
        else:
            stock = str(product["stock"])
        embed.add_field(name=product["title"], value=stock, inline=False)
    await ctx.send(embed=embed)


@client.command(name="replace")
async def replace(ctx, order_id, amount : int):
    if not has_permissions(ctx):
        embed = discord.Embed(title="No permission",
                              description="You don't have the permissions to execute this command",
                              color=discord.Color.red())
        await ctx.send(embed=embed)
        return
    order_information = get_order_information(order_id)
    if "status" in order_information and order_information["status"] is False:
        embed = discord.Embed(title="Order not found",
                              description="This order was not found",
                              color=discord.Color.red())
        await ctx.send(embed=embed)
        return

    product_info = order_information["product"]

    replacement =[]
    stock = product_info["accounts"]
    new_stock = []
    count = 0
    for i in range(len(stock)):
        if count < amount:
            replacement.append(stock[i]["account"])
        else:
            new_stock.append(stock[i]["account"])
        count = count+1

    data = {
        "title": product_info["title"],
        "price": product_info["price"],
        "type": product_info["type"],
        "email.enabled": True,
        "currency": product_info["currency"],
        "accounts": new_stock
    }

    up_header = {
        'Authorization': API_KEY,
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'User-Agent': 'Shoppy-Bot'
    }

    r = requests.post("https://shoppy.gg/api/v1/products/"+product_info["id"], json=data, headers=up_header,
                      verify=False)
    embed = discord.Embed(title="Replaced Order", description="Amount: "+str(amount), color=discord.Color.green())
    embed_c = 0
    for account in replacement:
        if embed_c % 25 == 0 and embed_c / 25 != 0:
            await ctx.send(embed=embed)
            embed = discord.Embed(title="Delivered Goods", description="Page " + str(round(embed_c / 25) + 1),
                                  color=discord.Color.blue())
        embed.add_field(name="Replaced Account", value=str(account), inline=False)
        embed_c = embed_c + 1
    await ctx.send(embed=embed)


@client.event
async def on_ready():
    printBanner()
    print("=> Command Prefix is " + PREFIX)
    print('=> Logged in as {0.user}'.format(client))
    game = discord.Game(name=PREFIX+"help")
    await client.change_presence(status=discord.Status.online, activity=game)
    set_default()
    update.start()


# Helper Functions
def printBanner():
    print("-------------------------------------------")
    print("SHOPPY BOT")
    print("-------------------------------------------")
    print("=> Started Shoppy Bot by Nergon#4972")


def set_default():
    global stock_list
    for product in get_products():
        stock_list[product["id"]] = int(product["stock"])


def has_permissions(ctx):
    for role_id in ROLES:
        role = discord.utils.get(ctx.guild.roles, id=role_id)
        if role in ctx.author.roles:
            return True
    return False


def get_order_information(order_id):
    r = requests.get(url="https://shoppy.gg/api/v1/orders/"+order_id, headers=header, verify=False)
    return json.loads(r.text)


def get_products():
    r = requests.get(url="https://shoppy.gg/api/v1/products/", headers=header, verify=False)
    return json.loads(r.text)


client.run(TOKEN)
