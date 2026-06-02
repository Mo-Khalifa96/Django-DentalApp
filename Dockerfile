#Stage 1 — Install dependencies for building
FROM python:3.12-slim AS builder

#Set working directory
WORKDIR /app

#Install system dependencies for building app
RUN apt-get update && apt-get install -y \
  gcc \
  build-essential \
  libpq-dev \
  libjpeg-dev \
  zlib1g-dev \
  && rm -rf /var/lib/apt/lists/*


#Install pipenv first
RUN pip install --upgrade pip pipenv

#Copy dependencies required by app 
COPY Pipfile Pipfile.lock /app/


#Set ENVIRONMENT argument 
ARG ENVIRONMENT

#Conditionally install dependencies based on environment
RUN if [ "$ENVIRONMENT" = "production" ] ; then \
  echo "Installing production dependencies..." && \
  pipenv install --system --deploy --ignore-pipfile; \
  elif [ "$ENVIRONMENT" = "development" ] ; then \
  echo "Installing cloud development dependencies..." && \
  pipenv install --system --deploy --dev; \
  elif [ "$ENVIRONMENT" = "local" ]; then \
  echo "Installing local development dependencies..." && \
  pipenv install --system --deploy --dev; \
  else \
  echo "No ENVIRONMENT set, skipping dependency installation..."; \
  fi

#or simplify to:
# RUN if [ "$ENVIRONMENT" = "production" ]; then \
#     pipenv install --system --deploy --ignore-pipfile; \
#     else \
#     pipenv install --system --deploy --dev; \
#     fi


#Stage 2 — Final image
FROM python:3.12-slim AS final

ENV PYTHONUNBUFFERED=1

#working directory
WORKDIR /app

#Copy only installed python packages from builder
COPY --from=builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=builder /usr/local/bin /usr/local/bin

#Install only runtime system deps (no gcc, no build-essential)
RUN apt-get update && apt-get install -y \
  libpq5 \
  libpq-dev \
  libjpeg-dev \
  zlib1g-dev \
  postgresql-client \
  ca-certificates \
  netcat-openbsd \
  inotify-tools \
  dnsutils \
  gettext \
  locales \
  tzdata \
  bash \
  nano \
  curl \
  && rm -rf /var/lib/apt/lists/*

#Copy permissions script
COPY permissions.sh /usr/local/bin/permissions.sh
RUN chmod +x /usr/local/bin/permissions.sh

#Copy full app
COPY . /app/

#Create backup and logs directories
RUN mkdir -p /logs    #/backups /logs

#Expose port
EXPOSE 8000

#Execute permissions.sh
ENTRYPOINT ["permissions.sh"]