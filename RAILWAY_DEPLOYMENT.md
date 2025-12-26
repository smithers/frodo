# Railway Deployment Guide

This guide will help you deploy the Frodo book recommendation application to Railway.

## Prerequisites

1. A Railway account (sign up at https://railway.app)
2. Your code pushed to a Git repository (GitHub, GitLab, or Bitbucket)

## Deployment Steps

### 1. Create a New Project on Railway

1. Go to https://railway.app and sign in
2. Click "New Project"
3. Select "Deploy from GitHub repo" (or your Git provider)
4. Select your repository

### 2. Add PostgreSQL Database

1. In your Railway project, click "New"
2. Select "Database" → "Add PostgreSQL"
3. Railway will automatically create a `DATABASE_URL` environment variable

### 3. Configure Environment Variables

In your Railway project settings, add the following environment variables:

- `SECRET_KEY`: Generate a new Django secret key (you can use `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
- `DEBUG`: Set to `False` for production
- `ALLOWED_HOSTS`: Set to your Railway domain (e.g., `your-app.railway.app`)

### 4. Deploy

Railway will automatically:
1. Detect the Python project
2. Install dependencies from `requirements.txt`
3. Run migrations (via Procfile)
4. Collect static files
5. Start the application with Gunicorn

### 5. Verify Deployment

1. Check the deployment logs in Railway dashboard
2. Visit your app URL (Railway provides one automatically)
3. Test the application functionality

## Post-Deployment

### Initial Data Setup

After deployment, you may want to:

1. Create a superuser:
   ```bash
   railway run python manage.py createsuperuser
   ```

2. Populate popular books:
   ```bash
   railway run python manage.py populate_popular_books --fetch-from-api
   ```

3. Import initial data (if needed):
   ```bash
   railway run python manage.py import_csv_data frodo_data_19Dec.csv
   ```

## Environment Variables Reference

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | Django secret key | Yes |
| `DEBUG` | Debug mode (False for production) | Yes |
| `ALLOWED_HOSTS` | Comma-separated list of allowed hosts | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Auto (from Railway) |

## Troubleshooting

### Static Files Not Loading

- Ensure `collectstatic` runs during deployment (it's in the Procfile)
- Check that `STATIC_ROOT` is set correctly in settings.py
- Verify WhiteNoise middleware is in `MIDDLEWARE`

### Database Connection Issues

- Verify PostgreSQL service is running in Railway
- Check that `DATABASE_URL` is set automatically
- Ensure `psycopg2-binary` is in requirements.txt

### Application Won't Start

- Check Railway logs for errors
- Verify all environment variables are set
- Ensure `gunicorn` is in requirements.txt
- Check that the Procfile is correct

## Monitoring

Railway provides:
- Real-time logs
- Metrics dashboard
- Automatic restarts on failure
- Custom domains

## Additional Resources

- [Railway Documentation](https://docs.railway.app)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/)

