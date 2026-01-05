## Docker Run
1. build
    ```bash
    docker build -t baha-scraper .
    ```
2. run
    ```bash
    docker run -d --name baha-scraper -p 15913:15913 baha-scraper
    ```