from flask import Flask, render_template, request, jsonify
import requests
import datetime
import re

app = Flask(__name__)

# Replace with your actual API keys
GEMINI_API_KEY = "AIzaSyBELORAAMgSdZtvxPMOkPAg2j80ApWtDa0"  # Replace with real key
WEATHER_API_KEY = "90c2f14be15207d796355e6823340af6"  # Replace with real key

# Conversation state
user_data = {
    "location": None,
    "date": None,
    "num_people": None,
    "return_date": None
}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json['message']
    current_date = datetime.datetime.now().date()

    if not user_data["location"]:
        user_data["location"] = user_msg
        return jsonify(reply=f"Great! You're going to {user_msg}. Please enter your travel date (DD-MM-YYYY):")

    elif not user_data["date"]:
        try:
            input_date = datetime.datetime.strptime(user_msg, "%d-%m-%Y").date()
            if input_date < current_date:
                return jsonify(reply="You cannot travel to the past! Please enter a future date (DD-MM-YYYY):")
            formatted_date = input_date.strftime("%Y-%m-%d")
            user_data["date"] = formatted_date
            return jsonify(reply="Thanks! How many people are going?")
        except ValueError:
            return jsonify(reply="Please enter a valid date in DD-MM-YYYY format:")

    elif not user_data["num_people"]:
        if user_msg.isdigit():
            user_data["num_people"] = int(user_msg)
            return jsonify(reply="When will you return? (DD-MM-YYYY or type 'Not sure')")
        else:
            return jsonify(reply="Please enter a valid number of people:")

    elif not user_data["return_date"]:
        if user_msg.lower() == "not sure":
            user_data["return_date"] = "Not sure"
        else:
            try:
                return_date = datetime.datetime.strptime(user_msg, "%d-%m-%Y").strftime("%Y-%m-%d")
                user_data["return_date"] = return_date
            except ValueError:
                return jsonify(reply="Please enter a valid return date in DD-MM-YYYY format or type 'Not sure'")

        # Fetch data
        location = user_data['location']
        date = user_data['date']
        people = user_data['num_people']
        travel_date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
        days_ahead = (travel_date - current_date).days

        # Weather check (assuming free tier gives ~7 days forecast)
        if days_ahead <= 7:
            weather_data = get_weather(location)
            if weather_data:
                weather_desc = weather_data["weather"][0]["description"].capitalize()
                temperature = weather_data["main"]["temp"]
                prompt = f"Packing List for {location} on {date} - {weather_desc}, {temperature:.2f}°C - for {people} people"
                packing_list = get_gemini_response(prompt)
                reply = f"The weather in {location} on {date} is expected to be {weather_desc} with {temperature:.2f}°C.<br><br>{packing_list}"
            else:
                prompt = f"Packing List for a trip to {location} on {date} for {people} people"
                packing_list = get_gemini_response(prompt)
                reply = f"Couldn't fetch weather data. Here's a general packing list:<br><br>{packing_list}"
        else:
            prompt = f"Packing List for a trip to {location} on {date} for {people} people"
            packing_list = get_gemini_response(prompt)
            reply = f"Weather is not available for this date ({date}). Here's a general packing list based on {location}:<br><br>{packing_list}"

        # Add final touches
        reply += "<br><br>Have a nice trip!<br><button onclick=\"location.reload()\">Start Again</button>"
        
        # Reset data for next user
        reset_user_data()
        return jsonify(reply=reply)

    else:
        return jsonify(reply="You've already entered all details. Please refresh to start a new session.")

def get_weather(location):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={WEATHER_API_KEY}&units=metric"
    try:
        res = requests.get(url)
        if res.status_code == 200:
            return res.json()
        else:
            return None
    except:
        return None

def get_gemini_response(prompt_text):
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-pro:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {"parts": [{"text": f"{prompt_text}\n\nGenerate a categorized, clean, and numbered packing list in the format:\nCategory: Clothing\n1. Jacket\n2. Socks\n\nCategory: Essentials\n1. Water Bottle\n2. Toothbrush\n\nAvoid long paragraphs."}]}
        ]
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            return format_gemini_response(text)
        else:
            print("Gemini API Error:", response.text)
            return "Error fetching packing list."
    except Exception as e:
        print("Exception in Gemini:", e)
        return "Gemini request failed."

def format_gemini_response(raw_text):
    lines = raw_text.strip().splitlines()
    formatted = []
    current_category = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.match(r'Category:|^[A-Z][a-z]+:', line):
            current_category = line
            formatted.append(f"<b>{line}</b>")
        elif re.match(r'^\d+[\.\)]', line) and current_category:
            formatted.append(line)
        else:
            formatted.append(line)
    return "<br>".join(formatted)  # Ensure sequential line-by-line output

def reset_user_data():
    for key in user_data:
        user_data[key] = None

if __name__ == '__main__':
    app.run(debug=True)