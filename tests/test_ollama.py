from app.providers import OllamaProvider


def main():
    provider = OllamaProvider()

    response = provider.generate(
        "llama3.2:3b",
        "Say hello to ERSELMETZ AI in one sentence."
    )

    print("🤖 Ollama Response:")
    print(response)


if __name__ == "__main__":
    main()