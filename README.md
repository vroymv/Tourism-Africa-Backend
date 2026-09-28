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

### Before deploying

1. Install Docker (including buildx) and AWS CLI v2; configure an IAM identity with permission to push ECR images and create/update Lambda functions and their roles. Check the identity with `aws sts get-caller-identity`. Use an IAM role rather than long-lived access keys when possible.
2. Pick an AWS Region that supports Lambda Function URLs. Create an AWS Budget alert so unexpected public API use does not go unnoticed.
3. Set your frontend origin (scheme, host, and port) as the function environment variable `CORS_ORIGINS`. For example, `https://app.example.com`; separate multiple origins with commas. Without it, only `http://localhost:3000` is allowed in browsers. This setting is **not** authentication: a public Function URL can still be called by anyone outside a browser.
4. Run `python -m pip install -r dev-requirements.txt` and `python -m pytest -q` in your Python environment. GET `/` and POST `/recommend/` (also `/countries` and `/countries/{country}`) should work locally before publishing.

### Build and push

From the repository root, substitute your AWS account ID, region and a unique release tag in the commands below. Keep ECR and Lambda in the same Region and account. On Apple Silicon the build deliberately targets x86_64 to match the function setting below.

```sh
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=123456789012
export RELEASE_TAG=v1
export IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/tourism-africa-api"

docker buildx build --platform linux/amd64 --provenance=false --load -t tourism-africa-api:${RELEASE_TAG} .
aws ecr create-repository --region "$AWS_REGION" --repository-name tourism-africa-api --image-scanning-configuration scanOnPush=true
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
docker tag tourism-africa-api:${RELEASE_TAG} "${IMAGE_URI}:${RELEASE_TAG}"
docker push "${IMAGE_URI}:${RELEASE_TAG}"
```

Create the ECR repository only on the first deployment. Keep at least one known-good release image in ECR for rollback; set an ECR lifecycle policy to clean up _older_ images when ready.

To smoke-test the image locally before pushing, run `docker run --platform linux/amd64 -p 9000:8080 tourism-africa-api:${RELEASE_TAG}` in another terminal, then invoke the Lambda runtime emulator:

```sh
curl -sS -X POST http://localhost:9000/2015-03-31/functions/function/invocations \
	-H 'Content-Type: application/json' \
	-d '{"version":"2.0","routeKey":"$default","rawPath":"/recommend/","rawQueryString":"","headers":{"content-type":"application/json"},"requestContext":{"http":{"method":"POST","path":"/recommend/","sourceIp":"127.0.0.1"},"domainName":"example.lambda-url.us-east-1.on.aws","stage":"$default"},"body":"{\"preferences\":{\"category\":\"natural\"},\"top_n\":3}","isBase64Encoded":false}'
```

### Create the function and URL (AWS console)

1. Open **Lambda → Functions → Create function → Container image**. Choose `tourism-africa-api`, the ECR image tagged above, architecture **x86_64**, and a new execution role with **AWSLambdaBasicExecutionRole** (CloudWatch logging). The ECR repository may require a Lambda image-retrieval policy if your IAM identity cannot grant it automatically. Do not attach a VPC for this API.
2. In **Configuration → General configuration**, start at **1,024 MB** memory and **30 seconds** timeout; tune them after observing CloudWatch duration and Max Memory Used. In **Environment variables**, set `CORS_ORIGINS` to your frontend origin. Leave Function URL CORS settings **off**; FastAPI supplies CORS headers and setting both can produce duplicates.
3. In **Configuration → Function URL**, create a URL with auth type **NONE** for this public MVP. Verify the function's resource policy permits both `lambda:InvokeFunctionUrl` and `lambda:InvokeFunction` via the URL (the console normally adds them). If public access is not intended, use IAM auth instead and implement authenticated frontend access. Consider reserved concurrency to limit runaway costs (excess requests receive HTTP 429) and CloudWatch alarms for errors, duration, and throttling.
4. Copy the HTTPS Function URL into your frontend's API base URL and set `FUNCTION_URL` to that address in your terminal (including the trailing `/`). Test `curl -i "${FUNCTION_URL}"`, `curl -i -X POST "${FUNCTION_URL}recommend/" -H 'Content-Type: application/json' -d '{"preferences":{"category":"natural"},"top_n":3}'`, and `curl -i "${FUNCTION_URL}docs"`. Check a browser preflight with `curl -i -X OPTIONS "${FUNCTION_URL}recommend/" -H 'Origin: https://app.example.com' -H 'Access-Control-Request-Method: POST' -H 'Access-Control-Request-Headers: content-type'` (substitute your configured origin).

### Updates and rollback

For each update, choose a new `RELEASE_TAG`, rebuild, tag, push, and explicitly deploy it:

```sh
aws lambda update-function-code --region "$AWS_REGION" --function-name tourism-africa-api --image-uri "${IMAGE_URI}:${RELEASE_TAG}"
aws lambda wait function-updated --region "$AWS_REGION" --function-name tourism-africa-api
```

Lambda resolves image tags to digests when deployed: pushing a new image with the same tag **does not update** the function. Smoke-test the URL after each update. To roll back, run the same update and wait commands with `RELEASE_TAG` set to the last known-good image tag; do not delete that image from ECR. Monitor the AWS Budget and CloudWatch logs/metrics after release.
