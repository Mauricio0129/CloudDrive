FROM  python:3.12-alpine AS base

ARG ENVIRONMENT
ENV PYROOT=/pyroot
ENV PYTHONUSERBASE=${PYROOT}

RUN  pip install pipenv
COPY Pipfile* ./
RUN if [ "$ENVIRONMENT" = "prod" ]; then PIP_USER=1 pipenv install --system --deploy --ignore-pipfile; \
    else PIP_USER=1 pipenv install --system --deploy --ignore-pipfile --dev; fi

FROM python:3.12-alpine

ENV PYROOT=/pyroot
ENV PYTHONUSERBASE=${PYROOT}
ENV PATH=${PATH}:${PYROOT}/bin

RUN addgroup -S myapp && adduser -S -G myapp user -u 1234
COPY --chown=user:myapp --from=base ${PYROOT}/ ${PYROOT}

RUN mkdir -p /usr/src/app
WORKDIR /usr/src
COPY --chown=user:myapp app ./app

USER user

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
