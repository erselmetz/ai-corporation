from app.providers import OllamaProvider


def main():
    provider = OllamaProvider(
        model="llama3.2:3b",
    )

    response = provider.generate(
        "Say hello to Erselmetz AI Corporation in one sentence."
    )

    print("🤖 Ollama Response:")
    print(response)


if __name__ == "__main__":
    main()