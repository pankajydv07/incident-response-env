from incident_response_env.server.app import app, main as package_main

app = app


def main(host: str = "0.0.0.0", port: int = 8000) -> None:
    package_main(host=host, port=port)


if __name__ == "__main__":
    main()
