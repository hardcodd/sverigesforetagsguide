import random
from dataclasses import dataclass

from django import forms
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils.translation import gettext as _
from slugify import slugify

IMPORTED_USERNAME_PREFIX = "m_"
RANDOM_NUMBER_MIN = 100
RANDOM_NUMBER_MAX = 999


@dataclass(frozen=True)
class ImportUser:
    full_name: str
    username: str | None


class ImportUserError(Exception):
    pass


def parse_import_user(raw_user: str) -> ImportUser:
    full_name, separator, username = raw_user.rpartition("/")

    if separator:
        username = username.strip()
        full_name = full_name.strip() or username
        if not username:
            raise forms.ValidationError(_("Username is required."))
    else:
        full_name = raw_user.strip()
        username = None

    user_model = get_user_model()
    first_name_field = user_model._meta.get_field("first_name")
    if first_name_field.max_length and len(full_name) > first_name_field.max_length:
        raise forms.ValidationError(
            _("Full name must contain at most %(max_length)s characters."),
            params={"max_length": first_name_field.max_length},
        )

    if username:
        username_field = user_model._meta.get_field(user_model.USERNAME_FIELD)
        if username_field.max_length and len(username) > username_field.max_length:
            raise forms.ValidationError(
                _("Username must contain at most %(max_length)s characters."),
                params={"max_length": username_field.max_length},
            )

    return ImportUser(full_name=full_name, username=username)


def _create_user(*, username: str, full_name: str):
    return get_user_model().objects.create_user(
        username=username,
        first_name=full_name,
    )


def _generated_username(full_name: str, random_number: int) -> str:
    user_model = get_user_model()
    username_field = user_model._meta.get_field(user_model.USERNAME_FIELD)
    prefix = f"{IMPORTED_USERNAME_PREFIX}{random_number}_"
    name_slug = slugify(full_name, separator="_")

    if username_field.max_length:
        name_slug = name_slug[: username_field.max_length - len(prefix)]

    return f"{prefix}{name_slug}"


def get_or_create_import_user(import_user: ImportUser):
    user_model = get_user_model()

    if import_user.username:
        try:
            return user_model.objects.get(username=import_user.username)
        except user_model.DoesNotExist:
            pass

        try:
            with transaction.atomic():  # pyright: ignore[reportGeneralTypeIssues]
                return _create_user(
                    username=import_user.username,
                    full_name=import_user.full_name,
                )
        except IntegrityError:
            return user_model.objects.get(username=import_user.username)

    existing_user = (
        user_model.objects.filter(
            username__startswith=IMPORTED_USERNAME_PREFIX,
            first_name=import_user.full_name,
        )
        .order_by("pk")
        .first()
    )
    if existing_user:
        return existing_user

    attempted_numbers = set()
    while len(attempted_numbers) <= RANDOM_NUMBER_MAX - RANDOM_NUMBER_MIN:
        random_number = random.randint(RANDOM_NUMBER_MIN, RANDOM_NUMBER_MAX)
        if random_number in attempted_numbers:
            continue
        attempted_numbers.add(random_number)
        username = _generated_username(import_user.full_name, random_number)

        try:
            with transaction.atomic():  # pyright: ignore[reportGeneralTypeIssues]
                return _create_user(
                    username=username,
                    full_name=import_user.full_name,
                )
        except IntegrityError:
            if user_model.objects.filter(username=username).exists():
                continue
            raise

    raise ImportUserError(_("Could not generate a unique username."))
