"""Bound input before Argon2, without accepting account privilege fields."""

from flask_wtf import FlaskForm
from wtforms import PasswordField, SelectField, StringField, SubmitField, TextAreaField
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


def postgres_text(form, field):
    if "\x00" in field.data:
        raise ValidationError("Null characters are not allowed.")


class TicketForm(FlaskForm):
    title = StringField(
        "Title", validators=[InputRequired(), Length(min=1, max=200), postgres_text]
    )
    description = TextAreaField(
        "Description",
        validators=[InputRequired(), Length(min=1, max=10000), postgres_text],
    )
    submit = SubmitField("Save ticket")


class EditTicketForm(TicketForm):
    status = SelectField(
        "Status",
        choices=[
            ("open", "Open"),
            ("in_progress", "In progress"),
            ("closed", "Closed"),
        ],
        validators=[InputRequired()],
    )


class CommentForm(FlaskForm):
    content = TextAreaField(
        "Comment", validators=[InputRequired(), Length(min=1, max=5000), postgres_text]
    )
    submit = SubmitField("Add comment")


class DeleteTicketForm(FlaskForm):
    submit = SubmitField("Confirm deletion of ticket and comments")


class ProfileForm(FlaskForm):
    display_name = StringField(
        "Display name",
        validators=[InputRequired(), Length(min=1, max=100), postgres_text],
    )
    submit = SubmitField("Save display name")


class AccountStatusForm(FlaskForm):
    submit = SubmitField("Confirm account status change")
