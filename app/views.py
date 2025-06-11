import matplotlib
matplotlib.use('Agg')  # Use a non-interactive backend for matplotlib

from app import app
import os
import json
import requests
import pandas as pd
from bs4 import BeautifulSoup
from matplotlib import pyplot as plt
from flask import render_template,request,redirect,url_for,send_file
from config import headers
from app import utils
import io

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
    
    opinions = pd.DataFrame.from_dict(all_opinions)
    opinions.stars = opinions.stars.apply(lambda s: s.split("/")[0].replace(",",".")).astype(float)
    opinions.useful = opinions.useful.astype(int)
    opinions.useless = opinions.useless.astype(int)
    stats = {
        "product_id": product_id,
        "product_name": product_name,
        "opinions_count": opinions.shape[0],
        "pros_count": int(opinions.pros.astype(bool).sum()),
        "cons_count": int(opinions.cons.astype(bool).sum()),
        "pros_cons_count": int((opinions.pros.astype(bool) & opinions.cons.astype(bool)).sum()),
        "avg_stars": float(opinions.stars.mean()),
        "pros": opinions.pros.explode().dropna().value_counts().to_dict(),
        "cons": opinions.cons.explode().dropna().value_counts().to_dict(),
        "recommendations": opinions.recommendation.value_counts(dropna=False).reindex(["Nie polecam", "Polecam", None], fill_value=0).to_dict()
    }
    if not os.path.exists("./app/data"):
        os.mkdir("./app/data")
    if not os.path.exists("./app/data/products"):
        os.mkdir("./app/data/products")
    with open (f"./app/data/products/{product_id}.json","w",encoding="utf-8") as file:
        json.dump(stats,file,ensure_ascii=False,indent=4)
    return redirect(url_for('product', product_id=product_id, product_name = product_name))

@app.route('/products')
def products():
    product_files = os.listdir("./app/data/products")
    products_list = []
    for filename in product_files:
        with open(f"./app/data/products/{filename}", "r", encoding="utf-8") as readfile:
            product = json.load(readfile)
            products_list.append(product)
    return render_template('products.html', products=products_list)

@app.route('/author')
def author():
    return render_template('author.html')

@app.route('/product/<product_id>')
def product(product_id):
    product_name = request.args.get('product_name') 
    opinions = pd.read_json(f"./app/data/opinions/{product_id}.json")
    
    # Konwersja DataFrame na listę słowników
    opinions_list = opinions.to_dict(orient="records")
    
    return render_template(
        "product.html",
        product_id=product_id,
        product_name=product_name,
        opinions=opinions_list 
    )

@app.route('/charts/<product_id>')
def charts(product_id):
    if not os.path.exists("./app/static/images"):
        os.mkdir("./app/static/images")
    if not os.path.exists("./app/static/images/charts"):
        os.mkdir("./app/static/images/charts")
    with open(f"./app/data/products/{product_id}.json", "r", encoding="utf-8") as readfile:
        stats = json.load(readfile)
        
    recommendations = pd.Series(stats["recommendations"])
    recommendations.plot.pie(
        label="",
        autopct="%.1f%%",
        title="Rozkład rekomendacji o produkcie",
        labels=["Nie polecam", "Polecam", "Brak rekomendacji"],
        legend=True,
        colors=["Red", "Green", "LightGray"],
    )
    plt.savefig(f"./app/static/images/charts/{stats['product_id']}_pie.png")
    plt.close()
    

    opinions = pd.read_json(f"./app/data/opinions/{product_id}.json")
    star_counts = opinions['stars'].value_counts().sort_index()
    star_counts.plot.bar(
        figsize=(10, 6),
        title="Liczba opinii dla każdej liczby gwiazdek",
        color="Gold",
        fontsize=12,
    )
    plt.ylabel("Liczba opinii")
    plt.xlabel("Liczba gwiazdek")
    plt.xticks(rotation=0)
    plt.savefig(f"./app/static/images/charts/{stats['product_id']}_stars_bar.png")
    plt.close()

    return render_template("charts.html", product_id=product_id, product_name=stats['product_name'])

@app.route('/download/<product_id>/<file_type>')
def download(product_id, file_type):
    path = f"./data/opinions/{product_id}.json"
    if file_type == "json":
        return send_file(path,as_attachment=True)
    elif file_type == "csv":
        path= f"./data/opinions/{product_id}.csv"
        df = pd.read_json(f"./app/data/opinions/{product_id}.json")
        buffer = io.StringIO()
        df.to_csv(buffer, index=False, encoding='utf-8')
        buffer.seek(0)
        return send_file(
            io.BytesIO(buffer.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f"{product_id}.csv"
        )
    elif file_type == "xlsx":
        buffer = io.BytesIO()
        df = pd.read_json(f"./app/data/opinions/{product_id}.json")
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Opinions')
        buffer.seek(0)
        return send_file(
            buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f"{product_id}.xlsx"
        )