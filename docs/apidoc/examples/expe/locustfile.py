import time

from locust import User, between, events, task


class QuickstartUser(User):
    wait_time = between(1, 2.5)

    @task
    def sleep1(self):
        # faking a 1 second request
        time.sleep(1)
        events.request.fire(
            request_type="noopclient",
            name="sleep1",
            response_time=1,
            response_length=0,
            response=None,
            context=None,
            exception=None,
        )
