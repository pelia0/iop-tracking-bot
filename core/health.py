import json
from datetime import datetime

class HealthMonitor:
    def __init__(self):
        self.consecutive_failures = 0
        self.last_successful_check = None
        self.total_checks = 0
        self.total_updates_found = 0
    
    def record_success(self):
        self.consecutive_failures = 0
        self.last_successful_check = datetime.now()
        self.total_checks += 1
    
    def record_failure(self) -> bool:
        """Повертає True якщо треба відправити алерт (3 помилки підряд)."""
        self.consecutive_failures += 1
        return self.consecutive_failures >= 3

health = HealthMonitor()
