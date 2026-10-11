from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _normalize(self, email):
        return (email or "").strip().lower()

    def get_by_natural_key(self, email):
        # Case-insensitive login: Ada@Example.com and ada@example.com are one account.
        return self.get(email__iexact=self._normalize(email))

    def _create(self, email, password, **extra):
        email = self._normalize(email)
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("Superuser must have is_staff=True and is_superuser=True.")
        return self._create(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """KULOSA account. Signs in with email. Defined before the first migration,
    as Django requires for a custom user model."""

    email = models.EmailField("email address", max_length=254, unique=True)
    full_name = models.CharField(max_length=120)
    phone = models.CharField("phone number", max_length=20, blank=True)

    is_active = models.BooleanField(default=True, help_text="Untick to suspend the account instead of deleting it.")
    is_staff = models.BooleanField(default=False, help_text="Can sign in to the admin site.")
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="unique_user_email_ci"),
        ]
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.full_name.split(" ")[0] if self.full_name else self.email

    def clean(self):
        super().clean()
        self.email = self.__class__.objects._normalize(self.email)
