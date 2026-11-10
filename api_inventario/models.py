# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class Dueno(models.Model):
    due_id = models.AutoField(primary_key=True)
    due_nombre = models.CharField(max_length=100, blank=True, null=True)
    due_estado = models.BooleanField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dueno'


class Productos(models.Model):
    pro_id = models.AutoField(primary_key=True)
    pro_nombre = models.CharField(max_length=100, blank=True, null=True)
    pro_codigo = models.CharField(max_length=100, blank=True, null=True)
    pro_ubicacion = models.ForeignKey('Ubicacion', models.DO_NOTHING, db_column='pro_ubicacion', blank=True, null=True)
    pro_precio = models.IntegerField(blank=True, null=True)
    pro_dueno = models.ForeignKey(Dueno, models.DO_NOTHING, db_column='pro_dueno', blank=True, null=True)    
    pro_cantidad = models.IntegerField(blank=True, null=True)
    pro_precio_oferta = models.CharField(max_length=50, blank=True, null=True)
    pro_tipo = models.ForeignKey('Tipo', models.DO_NOTHING, db_column='pro_tipo', blank=True, null=True)     
    pro_estado = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'productos'


class Tipo(models.Model):
    tip_id = models.AutoField(primary_key=True)
    tip_nombre = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tipo'


class Ubicacion(models.Model):
    ubi_id = models.AutoField(primary_key=True)
    ubi_nombre = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'ubicacion'


class Usuarios(models.Model):
    usu_id = models.AutoField(primary_key=True)
    usu_rut = models.CharField(unique=True, max_length=100)
    usu_clave = models.CharField(max_length=100, blank=True, null=True)
    usu_nombre = models.CharField(max_length=100, blank=True, null=True)
    usu_estado = models.BooleanField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'usuarios'

class Ventas(models.Model):
    ven_id = models.AutoField(primary_key=True)
    ven_fecha_registro = models.DateTimeField(blank=True, null=True)
    ven_productos = models.CharField(max_length=100)
    ven_monto_total = models.IntegerField(blank=True, null=True)
    ven_puesto = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'ventas'

class Puestos(models.Model):
    pue_id = models.AutoField(primary_key=True)
    pue_nombre = models.CharField(max_length=50)
    class Meta:
        managed = False
        db_table = 'puestos'

class VentasLibres(models.Model):
    vl_id = models.AutoField(primary_key=True)
    vl_nombre = models.CharField(max_length=100)
    vl_valor = models.IntegerField()
    vl_fecha_registro = models.DateTimeField(blank=True, null=True)
    vl_puesto = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'ventas_libres'


class CorreccionesLectura(models.Model):
    cl_id = models.AutoField(primary_key=True)
    cl_texto_crudo = models.CharField(max_length=100)
    cl_nombre_corregida = models.CharField(max_length=100)
    cl_valor_corregido = models.IntegerField()
    cl_fecha_registro = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'correcciones_lectura'
        constraints = [
            models.UniqueConstraint(fields=['cl_texto_crudo'], name='uq_correcciones_texto')
        ]

class UsoGemini(models.Model):
    ug_fecha = models.DateField(primary_key=True)
    ug_lecturas = models.IntegerField(default=0)
    ug_tokens = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = 'uso_gemini'