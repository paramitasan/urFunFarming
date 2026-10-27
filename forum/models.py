from django.db import models
from django.conf import settings

class Forum(models.Model):
    class Topic(models.TextChoices):
        PLANT_CARE = "plant_care", "Plant care"
        HYDROPONICS = "hydroponics", "Hydroponics"
        AEROPONICS  = "aeroponics", "Aeroponics"
        BALCONY = "balcony", "Balcony growing"
        WEATHER = "weather", "Weather"
        SEEDLINGS = "seedlings", "Seedlings"
        OTHER = "other", "Other"
        
    title = models.CharField(max_length=300)
    description = models.TextField(max_length=5000)
    topic = models.CharField(max_length=30, choices=Topic.choices, default=Topic.OTHER)
    image = models.ImageField(upload_to="forum/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)    # initiated once at Forum creation
    updated_at = models.DateTimeField(auto_now=True)        # initiated at the same time with created_at, updates
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forum_posts")

    class Meta:
        ordering = ["-created_at"]
    
    def __str__(self):
        return self.title

class Reply(models.Model):
    body = models.TextField(max_length=3000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name="replies")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forum_replies")

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.author} on {self.forum}"