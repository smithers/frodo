# Heroku Deployment Guide

This guide will help you deploy the Frodo book recommendation application to Heroku.

## Prerequisites

1. A Heroku account (sign up at https://heroku.com)
2. Heroku CLI installed (`brew install heroku/brew/heroku` on Mac)
3. Your code pushed to a Git repository

## Initial Setup

### 1. Login to Heroku

```bash
heroku login
```

### 2. Create a Heroku App

```bash
heroku create your-app-name
# Or let Heroku generate a name:
heroku create
```

### 3. Add PostgreSQL Database

```bash
heroku addons:create heroku-postgresql:mini
# Or for production:
heroku addons:create heroku-postgresql:standard-0
```

Heroku will automatically set the `DATABASE_URL` environment variable.

### 4. Set Environment Variables

```bash
# Generate a secret key
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Set environment variables
heroku config:set SECRET_KEY="your-secret-key-here"
heroku config:set DEBUG=False
heroku config:set ALLOWED_HOSTS="your-app-name.herokuapp.com"

# Set superuser credentials (optional - will be created during deployment)
heroku config:set DJANGO_SUPERUSER_USERNAME="czar"
heroku config:set DJANGO_SUPERUSER_EMAIL="czarniak@gmail.com"
heroku config:set DJANGO_SUPERUSER_PASSWORD="bjack44"
```

### 5. Deploy

```bash
git push heroku main
# Or if your branch is called master:
git push heroku master
```

Heroku will automatically:
1. Detect the Python project
2. Install dependencies from `requirements.txt`
3. Run migrations (via `release` phase in Procfile)
4. Collect static files (via `release` phase)
5. Start the application

### 6. Create Superuser (if not set via env vars)

```bash
heroku run python manage.py createsuperuser
```

Or use the non-interactive command:

```bash
heroku run python manage.py reset_superuser_password
```

## Useful Heroku Commands

### View Logs

```bash
heroku logs --tail
```

### Run Management Commands

```bash
heroku run python manage.py <command>
```

### Open Your App

```bash
heroku open
```

### Check Environment Variables

```bash
heroku config
```

### Run Django Shell

```bash
heroku run python manage.py shell
```

## Post-Deployment

### Create Superuser

If you didn't set the environment variables, create a superuser:

```bash
heroku run python manage.py createsuperuser
```

### Populate Data

```bash
heroku run python manage.py populate_popular_books --fetch-from-api
heroku run python manage.py import_csv_data frodo_data_19Dec.csv
```

## Troubleshooting

### Application Won't Start

- Check logs: `heroku logs --tail`
- Verify all environment variables are set: `heroku config`
- Ensure `gunicorn` is in `requirements.txt`

### Database Connection Issues

- Verify PostgreSQL addon is provisioned: `heroku addons`
- Check `DATABASE_URL` is set: `heroku config:get DATABASE_URL`
- Ensure `psycopg2-binary` is in `requirements.txt`

### Static Files Not Loading

- Static files are collected during the `release` phase
- Verify WhiteNoise is in `MIDDLEWARE` in `settings.py`
- Check `STATIC_ROOT` is set correctly

## Migration from Railway

If you're migrating from Railway:

1. Export your Railway environment variables
2. Set them in Heroku using `heroku config:set`
3. Update your git remote:
   ```bash
   git remote remove origin  # if needed
   git remote add heroku https://git.heroku.com/your-app-name.git
   ```
4. Push to Heroku: `git push heroku main`

## Additional Resources

- [Heroku Python Support](https://devcenter.heroku.com/articles/python-support)
- [Django on Heroku](https://devcenter.heroku.com/articles/django-app-configuration)
- [Heroku Postgres](https://devcenter.heroku.com/articles/heroku-postgresql)

