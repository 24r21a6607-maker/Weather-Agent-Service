from flask import Flask, request, jsonify, render_template_string
import requests

app = Flask(__name__)

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

# Weather codes -> human readable description (Open-Meteo WMO codes)
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snow fall", 73: "Moderate snow fall", 75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Weather Service</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { font-family: Arial, sans-serif; max-width: 480px; margin: 60px auto; text-align: center; }
    input { padding: 10px; width: 70%; font-size: 16px; }
    button { padding: 10px 16px; font-size: 16px; cursor: pointer; }
    #result { margin-top: 30px; font-size: 20px; }
    .temp { font-size: 48px; font-weight: bold; }
  </style>
</head>
<body>
  <h1>🌤️ Weather Service</h1>
  <p>Enter a city or place name to get the current weather in Celsius.</p>
  <input type="text" id="city" placeholder="e.g. Gandimaisamma" />
  <button onclick="getWeather()">Get Weather</button>
  <div id="result"></div>

  <script>
    async function getWeather() {
      const city = document.getElementById('city').value.trim();
      const resultDiv = document.getElementById('result');
      if (!city) {
        resultDiv.innerHTML = "Please enter a place name.";
        return;
      }
      resultDiv.innerHTML = "Loading...";
      try {
        const res = await fetch('/weather?city=' + encodeURIComponent(city));
        const data = await res.json();
        if (data.error) {
          resultDiv.innerHTML = "Error: " + data.error;
        } else {
          resultDiv.innerHTML = `
            <div class="temp">${data.temperature_celsius}°C</div>
            <div>${data.description}</div>
            <div>${data.location}</div>
          `;
        }
      } catch (e) {
        resultDiv.innerHTML = "Something went wrong. Please try again.";
      }
    }
  </script>
</body>
</html>
"""


def geocode_place(place_name):
    """Convert a place name into latitude/longitude using Open-Meteo's geocoding API."""
    params = {"name": place_name, "count": 1, "language": "en", "format": "json"}
    resp = requests.get(GEOCODE_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results")
    if not results:
        return None
    top = results[0]
    return {
        "latitude": top["latitude"],
        "longitude": top["longitude"],
        "name": top.get("name", place_name),
        "admin1": top.get("admin1", ""),
        "country": top.get("country", ""),
    }


def get_current_weather(lat, lon):
    """Fetch current weather (Celsius) for given coordinates."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": "true",
        "temperature_unit": "celsius",
        "windspeed_unit": "kmh",
    }
    resp = requests.get(WEATHER_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return data.get("current_weather")


@app.route("/")
def home():
    return render_template_string(HTML_PAGE)


@app.route("/weather", methods=["GET"])
def weather():
    city = request.args.get("city", "").strip()
    if not city:
        return jsonify({"error": "Please provide a 'city' query parameter, e.g. /weather?city=Gandimaisamma"}), 400

    try:
        place = geocode_place(city)
        if not place:
            return jsonify({"error": f"Could not find location '{city}'. Try a nearby larger town."}), 404

        current = get_current_weather(place["latitude"], place["longitude"])
        if not current:
            return jsonify({"error": "Weather data unavailable for this location."}), 502

        code = current.get("weathercode")
        description = WEATHER_CODES.get(code, "Unknown conditions")

        location_parts = [place["name"], place.get("admin1", ""), place.get("country", "")]
        location_str = ", ".join([p for p in location_parts if p])

        return jsonify({
            "location": location_str,
            "temperature_celsius": current.get("temperature"),
            "windspeed_kmh": current.get("windspeed"),
            "description": description,
            "query": city,
        })

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Upstream weather service error: {str(e)}"}), 502


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
