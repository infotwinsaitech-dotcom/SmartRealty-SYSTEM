from locust import HttpUser, task, between

class SmartRealtyUser(HttpUser):
    wait_time = between(1, 5)
    
    def on_start(self):
        self.client.post("/login/", {
            "username": "test_builder",
            "password": "test_password"
        })
    
    @task(3)
    def view_dashboard(self):
        self.client.get("/builder/dashboard/")
    
    @task(2)
    def view_leads(self):
        self.client.get("/builder/leads/")
    
    @task(1)
    def view_properties(self):
        self.client.get("/builder/properties/")