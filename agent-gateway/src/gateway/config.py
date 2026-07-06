from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    nats_url: str = "nats://localhost:4222"
    slo_url: str = "http://localhost:8000"
    port: int = 8004
    host: str = "0.0.0.0"
    log_level: str = "info"
    event_buffer_size: int = 1000
