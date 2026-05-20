import os
import json
import urllib.request
import datetime
from typing import Optional, Dict, Any

class WeatherProvider:
    def __init__(self):
        self.api_key = os.environ.get("WEATHER_API_KEY")
        self.base_url = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def get_historical_weather(self, lat: float, lon: float, dt: datetime.datetime) -> Optional[Dict[str, Any]]:
        if not self.is_configured():
            return None
            
        # Visual Crossing expects the date parameter in yyyy-MM-dd format
        date_str = dt.strftime("%Y-%m-%d")
        
        # We request data for the specific coordinate and date
        url = f"{self.base_url}/{lat},{lon}/{date_str}?key={self.api_key}&include=hours&unitGroup=us&contentType=json"
        req = urllib.request.Request(url, headers={'User-Agent': '(fulcradynamics.com, openclaw-agent)'})
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                
                days = data.get('days', [])
                if not days:
                    return None
                    
                hours = days[0].get('hours', [])
                if not hours:
                    return None
                
                closest_hour = None
                min_diff = float('inf')
                
                for h in hours:
                    # 'datetimeEpoch' is the UTC timestamp of the hour block
                    h_time = datetime.datetime.fromtimestamp(h['datetimeEpoch'], tz=datetime.timezone.utc)
                    diff = abs((h_time - dt).total_seconds())
                    
                    if diff < min_diff:
                        min_diff = diff
                        closest_hour = h
                        
                if closest_hour:
                    return {
                        "temp_f": closest_hour.get("temp"),
                        "temp_c": (closest_hour.get("temp", 32) - 32) * 5.0/9.0 if closest_hour.get("temp") is not None else None,
                        "condition": closest_hour.get("conditions", "Unknown"),
                        "humidity": closest_hour.get("humidity"),
                        "feelslike_f": closest_hour.get("feelslike")
                    }
                return None
                
        except Exception as e:
            # Fail silently to prevent breaking the main analyzer pipeline
            return None
