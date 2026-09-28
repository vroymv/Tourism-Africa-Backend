FROM public.ecr.aws/lambda/python:3.12

COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

COPY main.py african_touristic_sites.csv dataSet.csv ${LAMBDA_TASK_ROOT}/

CMD ["main.handler"]