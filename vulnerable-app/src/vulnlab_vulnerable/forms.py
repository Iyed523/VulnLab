"""Bound input before Argon2, without accepting account privilege fields."""

from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError

from .models import normalize_username


def username_valid(form, field):
    try:
        field.data = normalize_username(field.data)
    except ValueError:
        raise ValidationError(
            "Invalid username (3-32 normalized ASCII characters)."
        ) from None


class LoginForm(FlaskForm):
    username = StringField(
        "Username", validators=[InputRequired(), Length(max=128), username_valid]
    )
    password = PasswordField(
        "Password", validators=[InputRequired(), Length(min=12, max=128)]
    )
    submit = SubmitField("Log in")


class RegisterForm(LoginForm):
    display_name = StringField(
        "Display name", validators=[InputRequired(), Length(min=1, max=100)]
    )
    submit = SubmitField("Register")


class LogoutForm(FlaskForm):
    submit = SubmitField("Log out")
