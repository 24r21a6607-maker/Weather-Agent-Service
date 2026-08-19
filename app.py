import os
import requests

from fastapi import FastAPI
from pydantic import BaseModel, Field

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableLambda

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langserve import add_routes

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY environment variable is missing.")

llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    google_api_key=GOOGLE_API_KEY,
    temperature=0.3,
)

@tool
def get_current_weather(city: str) -> str:
    """Fetch current weather data for a given city using Open-Meteo API."""
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
        geo_res = requests.get(geo_url, timeout=10).json()

        if not geo_res.get("results"):
            return f"City '{city}' not found in Open-Meteo database. Try looking up the nearest major city (e.g., Hyderabad)."

        location = geo_res["results"][0]
        lat, lon = location["latitude"], location["longitude"]
        city_name = location["name"]
        country = location.get("country", "")

        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        weather_res = requests.get(weather_url, timeout=10).json()
        current = weather_res.get("current_weather", {})

        return (
            f"Current weather in {city_name}, {country}:\n"
            f"- Temperature: {current.get('temperature')}°C\n"
            f"- Wind Speed: {current.get('windspeed')} km/h"
        )
    except Exception as e:
        return f"Weather lookup failed: {str(e)}"

@tool
def recommend_clothing(temperature_celsius: float) -> str:
    """Provide outfit recommendations based on temperature."""
    prompt = f"Temperature: {temperature_celsius}°C. Suggest appropriate clothing briefly."
    response = llm.invoke(prompt)
    return response.content if hasattr(response, "content") else str(response)

tools = [get_current_weather, recommend_clothing]

# Updated prompt to handle locality fallbacks automatically
weather_agent = create_react_agent(
    model=llm,
    tools=tools,
    prompt=(
        "You are a helpful Weather and Outfit Advisory Agent. "
        "When checking weather for small towns or local areas that might not exist in standard APIs, "
        "search for the primary major metropolitan city nearby (for example, use Hyderabad for Gandimaisamma)."
    )
)

def process_query(user_input: str) -> str:
    """Handles raw user string inputs directly from LangServe Playground."""
    result = weather_agent.invoke({"messages": [HumanMessage(content=user_input)]})
    
    for msg in reversed(result.get("messages", [])):
        if msg.__class__.__name__ == "AIMessage" and getattr(msg, "content", ""):
            return msg.content
            
    return "No response generated."

app = FastAPI(title="Weather Advisory AI Agent")

# Expose as a direct string-to-string runnable for LangServe UI compatibility
add_routes(app, RunnableLambda(process_query), path="/weather-agent")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
