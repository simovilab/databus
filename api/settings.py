Python 3.10.1 (tags/v3.10.1:2cd268a, Dec  6 2021, 19:10:37) [MSC v.1929 64 bit (AMD64)] on win32
Type "help", "copyright", "credits" or "license()" for more information.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'simovi_db',  # Nombre de la base de datos
        'USER': 'simovi_user',  # Usuario de la base de datos
        'PASSWORD': 'your_password_here',  # Contraseña
        'HOST': 'localhost',
        'PORT': '5432',  # El puerto por defecto para PostgreSQL
    }
}

from django.db import models

# Modelo para Vehículos
class Vehicle(models.Model):
    model = models.CharField(max_length=255)
    year = models.IntegerField()
    vin = models.CharField(max_length=255, unique=True)
    license_plate = models.CharField(max_length=255)
    status = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.model

# Modelo para Dispositivos
class Device(models.Model):
    serial_number = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=255)
    model = models.CharField(max_length=255)
    status = models.CharField(max_length=50)
    assigned_to = models.ForeignKey('Person', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.serial_number

# Modelo para Personas
class Person(models.Model):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=50)
    address = models.TextField()
    status = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

# Modelo para Agencias
class Agency(models.Model):
    name = models.CharField(max_length=255)
    address = models.TextField()
    phone = models.CharField(max_length=50)
    status = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
