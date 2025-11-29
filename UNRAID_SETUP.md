# How to Install Your Custom Jelly Request on Unraid

Since you've modified the code to add MyAnimeList support and multiple lists, you need to build your own Docker image and tell Unraid to use it instead of the public one.

Here is the easiest path using **GitHub Container Registry (GHCR)**.

## Step 1: Fork and Push

Since you can't push to the original repository, you need your own copy.

1.  **Fork the repository** on GitHub:
    *   Go to [https://github.com/tophat17/jelly-request](https://github.com/tophat17/jelly-request)
    *   Click the **Fork** button (top right).

2.  **Update your local git to point to your fork**:
    *(Replace `YOUR_USERNAME` with your actual GitHub username)*
    ```powershell
    git remote set-url origin https://github.com/YOUR_USERNAME/jelly-request.git
    ```

3.  **Push your changes**:
    ```powershell
    git push -u origin feature/mal-support
    ```

## Step 2: Enable Auto-Building (The Easy Way)

Instead of installing Docker and building manually on your PC, let GitHub do it for free.

1.  Go to your forked repository on GitHub.
2.  Click **Actions**.
3.  If you see a generic "Docker image" workflow suggestion, click **Configure**.
    *   *Alternatively*, create a file in your repo at `.github/workflows/docker-publish.yml` with the content below:

```yaml
name: Docker

on:
  push:
    branches: [ "main", "feature/mal-support" ]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v3

      - name: Log in to the Container registry
        uses: docker/login-action@v2
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata (tags, labels) for Docker
        id: meta
        uses: docker/metadata-action@v4
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=raw,value=latest,enable=${{ github.ref == 'refs/heads/main' }}

      - name: Build and push Docker image
        uses: docker/build-push-action@v4
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
```

4.  Commit this file. GitHub will immediately start building your image.
5.  Wait for the Action to finish (green checkmark).

## Step 3: Update Unraid

Once the build finishes, your image is ready at `ghcr.io/YOUR_USERNAME/jelly-request:feature-mal-support`.

1.  Open your **Unraid Dashboard**.
2.  Go to the **Docker** tab.
3.  Click the **Jelly Request** icon -> **Edit**.
4.  Change **Repository** from `tophat17/jelly-request` to:
    ```text
    ghcr.io/YOUR_USERNAME/jelly-request:feature-mal-support
    ```
    *(Make sure to replace `YOUR_USERNAME` with your actual GitHub username, lowercase)*
5.  **Important:** Add the new `LIST_URLS` variable.
    *   Click **Add another Path, Port, Variable, Label or Device**.
    *   **Config Type:** Variable
    *   **Name:** LIST_URLS
    *   **Key:** LIST_URLS
    *   **Value:** `https://www.imdb.com/chart/moviemeter,https://myanimelist.net/anime/season`
6.  Click **Apply**.

Unraid will download your custom image and restart the container. You can check the logs to see it scraping both sites!
