from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel


class PremiumSubscription(models.Model):
    class Level(models.IntegerChoices):
        COMPETITOR = 0, _("Competitor")
        BASIC = 1, _("Basic")
        STANDARD = 2, _("Standard")
        PREMIUM = 3, _("Premium")

    organization = models.OneToOneField(
        "catalog.Organization",
        on_delete=models.CASCADE,
        related_name="premium_subscription",
        verbose_name=_("Organization"),
    )
    level = models.PositiveSmallIntegerField(
        choices=Level.choices,
        default=Level.BASIC,  # type: ignore
        verbose_name=_("Subscription Level"),
    )
    start_date = models.DateField(
        auto_now_add=True,
        verbose_name=_("Start Date"),
    )
    end_date = models.DateField(
        verbose_name=_("End Date"),
    )
    is_active = models.BooleanField(
        default=False,  # type: ignore
        verbose_name=_("Is Active"),
    )

    panels = [
        FieldPanel("organization"),
        FieldPanel("level"),
        FieldPanel("end_date"),
        FieldPanel("is_active"),
    ]

    @property
    def label(self):
        return str(self.Level(self.level).label)

    @property
    def is_premium(self):
        return self.level == self.Level.PREMIUM

    @property
    def is_standard(self):
        return self.level == self.Level.STANDARD

    @property
    def is_basic(self):
        return self.level == self.Level.BASIC

    @property
    def is_competitor(self):
        return self.level == self.Level.COMPETITOR

    @property
    def classname(self):
        if self.is_premium:
            return "premium"
        elif self.is_standard:
            return "standard"
        elif self.is_basic:
            return "basic"
        elif self.is_competitor:
            return "competitor"

    def __str__(self):
        return self.label

    def activate(self):
        self.is_active = True  # type: ignore
        self.save()

    def deactivate(self):
        self.is_active = False  # type: ignore
        self.save()

    def is_active_subscription(self):
        return self.start_date <= timezone.now().date() <= self.end_date

    class Meta:
        verbose_name = _("Premium Subscription")
        verbose_name_plural = _("Premium Subscriptions")
        ordering = ["end_date"]
