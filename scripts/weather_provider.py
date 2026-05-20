import os
import json
import urllib.request
import datetime
from typing import Optional, Dict, Any

class WeatherProvider:
    def __init__(self):
        self.api_key = os.environ.get("WEATHER_API_KEY")
        self.base_url = "http://api.weatherapi.com/v1/history.json"

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def get_historical_weather(self, lat: float, lon: float, dt: datetime.datetime) -> Optional[Dict[str, Any]]:
        if not self.is_configured():
            return None
            
        # WeatherAPI expects the date parameter in yyyy-MM-dd format
        date_str = dt.strftime("%Y-%m-%d")
        
        url = f"{self.base_url}?key={self.api_key}&q={lat},{lon}&dt={date_str}"
        req = urllib.request.Request(url, headers={'User-Agent': '(fulcradynamics.com, openclaw-agent)'})
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                
                # WeatherAPI returns hourly data for the requested day. 
                # We need to find the specific hour that matches our dt.
                forecast_day = data.get('forecast', {}).get('forecastday', [])
                if not forecast_day:
                    return None
                    
                hours = forecast_day[0].get('hour', [])
                
                closest_hour = None
                min_diff = float('inf')
                
                for h in hours:
                    # 'time_epoch' is the UTC timestamp of the hour block
                    h_time = datetime.datetime.fromtimestamp(h['time_epoch'], tz=datetime.timezone.utc)
                    diff = abs((h_time - dt).total_seconds())
                    
                    if diff < min_diff:
                        min_diff = diff
                        closest_hour = h
                        
                if closest_hour:
                    return {
                        "temp_f": closest_hour.get("temp_f"),
                        "temp_c": closest_hour.get("temp_c"),
                        "condition": closest_hour.get("condition", {}).get("text", "Unknown"),
                        "humidity": closest_hour.get("humidity"),
                        "feelslike_f": closest_hour.get("feelslike_f")
                    }
                return None
                
        except Exception as e:
            # We fail silently so it doesn't break the main analyzer pipeline
            return None
