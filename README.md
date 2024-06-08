# Omni WebUI (Fork of Omni WebUI) 👋

![GitHub stars](https://img.shields.io/github/stars/omni-webui/omni-webui?style=social)
![GitHub forks](https://img.shields.io/github/forks/omni-webui/omni-webui?style=social)
![GitHub watchers](https://img.shields.io/github/watchers/omni-webui/omni-webui?style=social)
![GitHub repo size](https://img.shields.io/github/repo-size/omni-webui/omni-webui)
![GitHub language count](https://img.shields.io/github/languages/count/omni-webui/omni-webui)
![GitHub top language](https://img.shields.io/github/languages/top/omni-webui/omni-webui)
![GitHub last commit](https://img.shields.io/github/last-commit/omni-webui/omni-webui?color=red)
![Hits](https://hits.seeyoufarm.com/api/count/incr/badge.svg?url=https%3A%2F%2Fgithub.com%2Follama-webui%2Follama-wbui&count_bg=%2379C83D&title_bg=%23555555&icon=&icon_color=%23E7E7E7&title=hits&edge_flat=false)

Omni WebUI is an [extensible](https://github.com/omni-webui/pipelines), feature-rich, and user-friendly self-hosted WebUI designed to operate entirely offline. It supports various LLM runners, including Ollama and OpenAI-compatible APIs. For more information, be sure to check out our [Omni WebUI Documentation](https://docs.omni-webui.com/).

![Omni WebUI Demo](./demo.gif)

## Key Features of Omni WebUI ⭐

- 🚀 **Effortless Setup**: Install seamlessly using Docker or Kubernetes (kubectl, kustomize or helm) for a hassle-free experience with support for both `:ollama` and `:cuda` tagged images.

- 🤝 **Ollama/OpenAI API Integration**: Effortlessly integrate OpenAI-compatible APIs for versatile conversations alongside Ollama models. Customize the OpenAI API URL to link with **LMStudio, GroqCloud, Mistral, OpenRouter, and more**.

- 🧩 **Pipelines, Omni WebUI Plugin Support**: Seamlessly integrate custom logic and Python libraries into Omni WebUI using [Pipelines Plugin Framework](https://github.com/omni-webui/pipelines). Launch your Pipelines instance, set the OpenAI URL to the Pipelines URL, and explore endless possibilities. [Examples](https://github.com/omni-webui/pipelines/tree/main/examples) include **Function Calling**, User **Rate Limiting** to control access, **Usage Monitoring** with tools like Langfuse, **Live Translation with LibreTranslate** for multilingual support, **Toxic Message Filtering** and much more.

- 📱 **Responsive Design**: Enjoy a seamless experience across Desktop PC, Laptop, and Mobile devices.

- 📱 **Progressive Web App (PWA) for Mobile**: Enjoy a native app-like experience on your mobile device with our PWA, providing offline access on localhost and a seamless user interface.

- ✒️🔢 **Full Markdown and LaTeX Support**: Elevate your LLM experience with comprehensive Markdown and LaTeX capabilities for enriched interaction.

- 🛠️ **Model Builder**: Easily create Ollama models via the Web UI. Create and add custom characters/agents, customize chat elements, and import models effortlessly through [Omni WebUI Community](https://omni-webui.com/) integration.

- 📚 **Local RAG Integration**: Dive into the future of chat interactions with groundbreaking Retrieval Augmented Generation (RAG) support. This feature seamlessly integrates document interactions into your chat experience. You can load documents directly into the chat or add files to your document library, effortlessly accessing them using the `#` command before a query.

- 🔍 **Web Search for RAG**: Perform web searches using providers like `SearXNG`, `Google PSE`, `Brave Search`, `serpstack`, and `serper`, and inject the results directly into your chat experience.

- 🌐 **Web Browsing Capability**: Seamlessly integrate websites into your chat experience using the `#` command followed by a URL. This feature allows you to incorporate web content directly into your conversations, enhancing the richness and depth of your interactions.

- 🎨 **Image Generation Integration**: Seamlessly incorporate image generation capabilities using options such as AUTOMATIC1111 API or ComfyUI (local), and OpenAI's DALL-E (external), enriching your chat experience with dynamic visual content.

- ⚙️ **Many Models Conversations**: Effortlessly engage with various models simultaneously, harnessing their unique strengths for optimal responses. Enhance your experience by leveraging a diverse set of models in parallel.

- 🔐 **Role-Based Access Control (RBAC)**: Ensure secure access with restricted permissions; only authorized individuals can access your Ollama, and exclusive model creation/pulling rights are reserved for administrators.

- 🌐🌍 **Multilingual Support**: Experience Omni WebUI in your preferred language with our internationalization (i18n) support. Join us in expanding our supported languages! We're actively seeking contributors!

- 🌟 **Continuous Updates**: We are committed to improving Omni WebUI with regular updates, fixes, and new features.

Want to learn more about Omni WebUI's features? Check out our [Omni WebUI documentation](https://docs.omni-webui.com/features) for a comprehensive overview!

## 🔗 Also Check Out Omni WebUI Community!

Don't forget to explore our sibling project, [Omni WebUI Community](https://omni-webui.com/), where you can discover, download, and explore customized Modelfiles. Omni WebUI Community offers a wide range of exciting possibilities for enhancing your chat interactions with Omni WebUI! 🚀

## How to Install 🚀

> [!NOTE]  
> Please note that for certain Docker environments, additional configurations might be needed. If you encounter any connection issues, our detailed guide on [Omni WebUI Documentation](https://docs.omni-webui.com/) is ready to assist you.

### Quick Start with Docker 🐳

> [!WARNING]
> When using Docker to install Omni WebUI, make sure to include the `-v omni-webui:/app/backend/data` in your Docker command. This step is crucial as it ensures your database is properly mounted and prevents any loss of data.

> [!TIP]  
> If you wish to utilize Omni WebUI with Ollama included or CUDA acceleration, we recommend utilizing our official images tagged with either `:cuda` or `:ollama`. To enable CUDA, you must install the [Nvidia CUDA container toolkit](https://docs.nvidia.com/dgx/nvidia-container-runtime-upgrade/) on your Linux/WSL system.

### Installation with Default Configuration

- **If Ollama is on your computer**, use this command:

  ```bash
  docker run -d -p 3000:8080 --add-host=host.docker.internal:host-gateway -v omni-webui:/app/backend/data --name omni-webui --restart always ghcr.io/omni-webui/omni-webui:main
  ```

- **If Ollama is on a Different Server**, use this command:

  To connect to Ollama on another server, change the `OLLAMA_BASE_URL` to the server's URL:

  ```bash
  docker run -d -p 3000:8080 -e OLLAMA_BASE_URL=https://example.com -v omni-webui:/app/backend/data --name omni-webui --restart always ghcr.io/omni-webui/omni-webui:main
  ```

  - **To run Omni WebUI with Nvidia GPU support**, use this command:

  ```bash
  docker run -d -p 3000:8080 --gpus all --add-host=host.docker.internal:host-gateway -v omni-webui:/app/backend/data --name omni-webui --restart always ghcr.io/omni-webui/omni-webui:cuda
  ```

### Installation for OpenAI API Usage Only

- **If you're only using OpenAI API**, use this command:

  ```bash
  docker run -d -p 3000:8080 -e OPENAI_API_KEY=your_secret_key -v omni-webui:/app/backend/data --name omni-webui --restart always ghcr.io/omni-webui/omni-webui:main
  ```

### Installing Omni WebUI with Bundled Ollama Support

This installation method uses a single container image that bundles Omni WebUI with Ollama, allowing for a streamlined setup via a single command. Choose the appropriate command based on your hardware setup:

- **With GPU Support**:
  Utilize GPU resources by running the following command:

  ```bash
  docker run -d -p 3000:8080 --gpus=all -v ollama:/root/.ollama -v omni-webui:/app/backend/data --name omni-webui --restart always ghcr.io/omni-webui/omni-webui:ollama
  ```

- **For CPU Only**:
  If you're not using a GPU, use this command instead:

  ```bash
  docker run -d -p 3000:8080 -v ollama:/root/.ollama -v omni-webui:/app/backend/data --name omni-webui --restart always ghcr.io/omni-webui/omni-webui:ollama
  ```

Both commands facilitate a built-in, hassle-free installation of both Omni WebUI and Ollama, ensuring that you can get everything up and running swiftly.

After installation, you can access Omni WebUI at [http://localhost:3000](http://localhost:3000). Enjoy! 😄

### Other Installation Methods

We offer various installation alternatives, including non-Docker native installation methods, Docker Compose, Kustomize, and Helm. Visit our [Omni WebUI Documentation](https://docs.omni-webui.com/getting-started/) or join our [Discord community](https://discord.gg/5rJgQTnV4s) for comprehensive guidance.

### Troubleshooting

Encountering connection issues? Our [Omni WebUI Documentation](https://docs.omni-webui.com/troubleshooting/) has got you covered. For further assistance and to join our vibrant community, visit the [Omni WebUI Discord](https://discord.gg/5rJgQTnV4s).

#### Omni WebUI: Server Connection Error

If you're experiencing connection issues, it’s often due to the WebUI docker container not being able to reach the Ollama server at 127.0.0.1:11434 (host.docker.internal:11434) inside the container . Use the `--network=host` flag in your docker command to resolve this. Note that the port changes from 3000 to 8080, resulting in the link: `http://localhost:8080`.

**Example Docker Command**:

```bash
docker run -d --network=host -v omni-webui:/app/backend/data -e OLLAMA_BASE_URL=http://127.0.0.1:11434 --name omni-webui --restart always ghcr.io/omni-webui/omni-webui:main
```

### Keeping Your Docker Installation Up-to-Date

In case you want to update your local Docker installation to the latest version, you can do it with [Watchtower](https://containrrr.dev/watchtower/):

```bash
docker run --rm --volume /var/run/docker.sock:/var/run/docker.sock containrrr/watchtower --run-once omni-webui
```

In the last part of the command, replace `omni-webui` with your container name if it is different.

### Moving from Ollama WebUI to Omni WebUI

Check our Migration Guide available in our [Omni WebUI Documentation](https://docs.omni-webui.com/migration/).

## What's Next? 🌟

Discover upcoming features on our roadmap in the [Omni WebUI Documentation](https://docs.omni-webui.com/roadmap/).

## Supporters ✨

A big shoutout to our amazing supporters who's helping to make this project possible! 🙏

### Platinum Sponsors 🤍

- We're looking for Sponsors!

### Acknowledgments

Special thanks to [Prof. Lawrence Kim](https://www.lhkim.com/) and [Prof. Nick Vincent](https://www.nickmvincent.com/) for their invaluable support and guidance in shaping this project into a research endeavor. Grateful for your mentorship throughout the journey! 🙌

## License 📜

This project is licensed under the [MIT License](LICENSE) - see the [LICENSE](LICENSE) file for details. 📄

## Support 💬

If you have any questions, suggestions, or need assistance, please open an issue or join our
[Omni WebUI Discord community](https://discord.gg/5rJgQTnV4s) to connect with us! 🤝

## Star History

<a href="https://star-history.com/#omni-webui/omni-webui&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=omni-webui/omni-webui&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=omni-webui/omni-webui&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=omni-webui/omni-webui&type=Date" />
  </picture>
</a>

---

Created by [Ziya Tang](https://github.com/tcztzy) - Let's make Omni WebUI even more amazing together! 💪
