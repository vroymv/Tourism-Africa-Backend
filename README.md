# FastAPI Template

This sample repo contains the recommended structure for a Python FastAPI project. In this sample, we use `fastapi` to build a web application and the `pytest` to run tests.

For a more in-depth tutorial, see our [Fast API tutorial](https://code.visualstudio.com/docs/python/tutorial-fastapi).

The code in this repo aims to follow Python style guidelines as outlined in [PEP 8](https://peps.python.org/pep-0008/).

## Set up instructions

This sample makes use of Dev Containers, in order to leverage this setup, make sure you have [Docker installed](https://www.docker.com/products/docker-desktop).

To successfully run this example, we recommend the following VS Code extensions:

- [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
- [Python](https://marketplace.visualstudio.com/items?itemName=ms-python.python)
- [Python Debugger](https://marketplace.visualstudio.com/items?itemName=ms-python.debugpy)
- [Pylance](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance)

In addition to these extension there a few settings that are also useful to enable. You can enable to following settings by opening the Settings editor (`Ctrl+,`) and searching for the following settings:

- Python > Analysis > **Type Checking Mode** : `basic`
- Python > Analysis > Inlay Hints: **Function Return Types** : `enable`
- Python > Analysis > Inlay Hints: **Variable Types** : `enable`

## Running the sample

- Open the template folder in VS Code (**File** > **Open Folder...**)
- Open the Command Palette in VS Code (**View > Command Palette...**) and run the **Dev Container: Reopen in Container** command.
- Run the app using the Run and Debug view or by pressing `F5`
- `Ctrl + click` on the URL that shows up on the terminal to open the running application
- Test the API functionality by navigating to `/docs` URL to view the Swagger UI
- Configure your Python test in the Test Panel or by triggering the **Python: Configure Tests** command from the Command Palette
- Run tests in the Test Panel or by clicking the Play Button next to the individual tests in the `test_main.py` file

## AWS Lambda deployment

This API can run on AWS Lambda using a private Amazon ECR image and a public HTTPS Function URL. Requests may be slower after an idle period (cold starts). The bundled CSV datasets are loaded once per execution environment; there is no database or S3 dependency. Lambda does not run the Heroku `Procfile` or a listening Uvicorn process.

### Automated deployment

Application releases come only from `.github/workflows/deploy.yml`. A push to `main` or a manual workflow dispatch performs these steps:

1. Run the test suite with Python 3.12.
2. Obtain temporary AWS credentials through GitHub OIDC. No AWS access keys are stored in GitHub.
3. Build the x86_64 Lambda image from the committed source and push it to the private `tourism-africa-api` ECR repository using both the Git commit SHA and `latest` tags.
4. Create the Lambda function on the first release or update it on later releases, then configure its environment and public Function URL.
5. Smoke-test GET `/` and publish the Function URL in the workflow summary.

The AWS resources are in account `602787432465`, Region `eu-west-1`. The `GitHubActionsTourismAfricaDeploy` role trusts only the `production` environment of `vroymv/Tourism-Africa-Backend`; its inline policy is limited to this ECR repository, Lambda function, and execution role.

Set the GitHub repository variable `CORS_ORIGINS` to the production frontend origin, such as `https://app.example.com`. Separate multiple origins with commas. Until it is set, deployments use `http://localhost:3000`. This setting is **not** authentication: anyone can invoke the public Function URL outside a browser.

Create an AWS Budget alert so unexpected public API use does not go unnoticed. Consider Lambda reserved concurrency and CloudWatch alarms for errors, duration, and throttling.

### Local verification

Run `python -m pip install -r dev-requirements.txt` and `python -m pytest -q`. GET `/`, POST `/recommend/`, `/countries`, and `/countries/{country}` should work locally before publishing.

The following build checks the same image locally but does not upload it to AWS:

```sh
docker buildx build --platform linux/amd64 --provenance=false --load -t tourism-africa-api:local .
```

Run `docker run --platform linux/amd64 -p 9000:8080 tourism-africa-api:local` in another terminal, then invoke the Lambda runtime emulator:

```sh
curl -sS -X POST http://localhost:9000/2015-03-31/functions/function/invocations \
  -H 'Content-Type: application/json' \
  -d '{"version":"2.0","routeKey":"$default","rawPath":"/recommend/","rawQueryString":"","headers":{"content-type":"application/json"},"requestContext":{"http":{"method":"POST","path":"/recommend/","sourceIp":"127.0.0.1"},"domainName":"example.lambda-url.us-east-1.on.aws","stage":"$default"},"body":"{\"preferences\":{\"category\":\"natural\"},\"top_n\":3}","isBase64Encoded":false}'
```

### Updates and rollback

Every successful push to `main` deploys its immutable commit-SHA image. Use the **Deploy to AWS Lambda** workflow's manual dispatch to retry a failed deployment. To roll back through the same audited path, revert the bad commit on `main`; the resulting commit triggers a deployment containing the previous application state. The ECR lifecycle policy retains the 10 newest images. Monitor the AWS Budget and CloudWatch logs and metrics after release.
