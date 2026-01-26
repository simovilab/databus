<img width="250" alt="databus" src="https://github.com/user-attachments/assets/b2ad45ac-83e5-44cf-a93e-898868763530" />

# Django App for GTFS

![Django](https://img.shields.io/badge/Django-5.2-blue)

Django app for managing GTFS models and utilities for use in Databús and also Infobús.

```python
# settings.py
INSTALLED_APPS = [
    ...
    'gtfs',
]
```

> [!IMPORTANT]
> The app uses composite primary keys in the models, available since Django 5.2.
