from app import app
import os
import json
import requests
import pandas as pd
from bs4 import BeautifulSoup
from flask import render_template,request,redirect,url_for
from config import headers
from app import utils

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/extract')
def display_form():
    return render_template("extract.html")

@app.route("/extract",methods=['POST'])
def extract():
    product_id = request.form.get('product_id')
    next_page = (f"https://www.ceneo.pl/{product_id}#tab=reviews")
    response = requests.get(next_page,headers=headers)
    if response.status_code == 200:
        page_dom = BeautifulSoup(response.text, "html.parser")
        product_name = utils.extract_feature(page_dom,"h1")
        opinions_count = utils.extract_feature(page_dom,"a.product-review__link > span")
        if not opinions_count:
            return render_template("extract.html",error="Dla produktu o podanym ID nie ma jeszcze żadnych opinii.")
    else:
        return render_template("extract.html",error="Nie znaleziono produktu o podanym ID.")
    all_opinions = []
    while next_page:
        print(next_page)
        response = requests.get(next_page,headers=headers)
        if response.status_code == 200:
            page_dom = BeautifulSoup(response.text, "html.parser")
            opinions = page_dom.select("div.js_product-review:not(.user-post--highlight)")
            for opinion in opinions:
                single_opinion = {
                    key: utils.extract_feature(opinion,*value)
                    for key, value in utils.selectors.items()
                }
                all_opinions.append(single_opinion)
            try:
                next_page = "https://www.ceneo.pl" + utils.extract_feature(page_dom,"a.pagination__next","href")
            except TypeError:
                next_page = None
                print("Brak kolejnej strony.")
        else:
            print(f"{response.status_code}")
    if not os.path.exists("./app/data"):
        os.mkdir("./app/data")
    
    if not os.path.exists("./app/data/opinions"):
        os.mkdir("./app/data/opinions")
        
    with open (f"./app/data/opinions/{product_id}.json","w",encoding="utf-8") as file:
        json.dump(all_opinions,file,ensure_ascii=False,indent=4)
        
    return redirect(url_for('product', product_id=product_id, product_name=product_name))

@app.route('/products')
def products():
    return render_template('products.html')

@app.route('/author')
def author():
    return render_template('author.html')

@app.route('/product/<product_id>')
def product(product_id):
    product_name = request.args.get('product_name') 
    opinions = pd.read_json(f"./app/data/opinions/{product_id}.json")
    return render_template("product.html",product_id=product_id, product_name=product_name, opinions=opinions.to_html(classes="display",table_id="opinions"))
