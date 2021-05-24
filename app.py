import sys
import requests
import time

from json import loads
from flask import Flask, render_template, request, flash, redirect
from bs4 import BeautifulSoup, Tag
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy


def call_api(city: str):
    # This website uses OpenWeather to get the current weather data using the city name provided
    # More info on https://openweathermap.org/current
    # To use this API you need an API KEY
    # https://openweathermap.org/appid
    api_key = 'todo: Place your API Key here'
    url = 'http://api.openweathermap.org/data/2.5/weather'

    response = requests.post(url, params={'q': city, 'appid': api_key})
    return loads(response.text)


def kelvin_to_celsius(k: float):
    return round(k - 273.15, 1)


def find_image(city: str, daytime: str):
    # -map -geographic -people -> ignore maps, result related to geography and images of people walking on the streets
    # tbm = isch -> search for images
    # tbs = iar:xw -> only panoramic images
    # tbs = iar:w -> only horizontal images
    # safe = active -> with safe search active

    params = {'q': f'{city} {daytime} -map -geographic -people -news', 'tbm': 'isch', 'safe': 'active', 'tbs': 'iar:w'}
    response = requests.get('https://www.google.com/search', params=params)
    soup = BeautifulSoup(response.content, 'html.parser')

    images: list[Tag] = soup.find_all('img')

    for image in images:
        # If the image isn't Google's logo
        if image.get('alt').lower() != 'google':
            chosen_image = image
            break
    else:
        # In case no images are found, returns an image os a city
        return 'https://www.visiteosusa.com.br/sites/default/files/styles/hero_l_x2/public/images/hero_media_image/2017-06/de6f732d8950b74b550d885beab53c37.jpeg?itok=AHJDbUok'

    source = chosen_image.get('src')

    # Sleep 50ms to avoid sending too many requests
    time.sleep(0.05)
    return source


def get_city_data(city_name: str):
    api_response = call_api(city_name)

    city_datetime = datetime.utcnow() + timedelta(seconds=api_response['timezone'])
    city = City.query.filter_by(name=city_name).first()

    if 6 <= city_datetime.hour <= 18:
        img = city.img_day
    else:
        img = city.img_night

    info = {'country': api_response['sys']['country'],
            'temp': kelvin_to_celsius(api_response['main']['temp']),
            'status': api_response['weather'][0]['main'],
            'img': img,
            'description': api_response['weather'][0]['description'].capitalize(),
            'feels_like': kelvin_to_celsius(api_response['main']['feels_like']),
            'temp_min': kelvin_to_celsius(api_response['main']['temp_min']),
            'temp_max': kelvin_to_celsius(api_response['main']['temp_max']),
            'pressure': api_response['main']['pressure'],
            'humidity': api_response['main']['humidity']}
    return info


def get_id():
    return len(City.query.all())


def get_all_cities():
    return map(lambda item: item.name, City.query.all())


app = Flask(__name__)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///weather.db'
app.config['SECRET_KEY'] = 'super secret key'
db = SQLAlchemy(app)


class City(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), nullable=False, unique=True)
    img_day = db.Column(db.String(200))
    img_night = db.Column(db.String(200))


# Used to create the database. Run this once.
# db.create_all()


@app.route('/', methods=['POST'])
def add():
    city_name: str = request.form['city_name']

    api_response: dict = call_api(city_name)
    if api_response['cod'] != 200:
        flash("The city doesn't exist!")
    else:
        city = City(id=get_id(), name=city_name, img_day=find_image(city_name, ''),
                    img_night=find_image(city_name, 'night'))

        if City.query.filter_by(name=city_name).first() is None:
            db.session.add(city)
            db.session.commit()
        else:
            flash('The city has already been added to the list!')
    return redirect('/')


@app.route('/delete/<city_name>', methods=['GET', 'POST'])
def delete(city_name):
    city = City.query.filter_by(name=city_name).first()
    db.session.delete(city)
    db.session.commit()
    return redirect('/')


@app.route('/', methods=['GET'])
def index():
    # print(City.query.all())
    weather = {city_name: get_city_data(city_name) for city_name in get_all_cities()}
    return render_template('index.html', weather=weather)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        arg_host, arg_port = sys.argv[1].split(':')
        app.run(host=arg_host, port=arg_port)
    else:
        app.run()
