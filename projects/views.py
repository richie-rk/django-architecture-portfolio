from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django_ratelimit.decorators import ratelimit

from .forms import ContactForm
from .models import Category, Project


def homepage(request):
    featured = list(
        Project.objects.filter(is_featured=True)
        .select_related('category')
        .order_by('order', '-year_completed')[:6]
    )
    return render(request, 'projects/homepage.html', {'featured_projects': featured})


def projects_list(request):
    categories = Category.objects.all().order_by('order', 'name')
    project_qs = Project.objects.select_related('category').order_by(
        'order', '-year_completed'
    )

    selected_category = None
    category_slug = request.GET.get('category')
    if category_slug:
        selected_category = next(
            (c for c in categories if c.slug == category_slug), None
        )
        if selected_category:
            project_qs = project_qs.filter(category=selected_category)

    return render(
        request,
        'projects/projects_list.html',
        {
            'categories': categories,
            'projects': project_qs,
            'selected_category': selected_category,
        },
    )


def project_detail(request, slug):
    project = get_object_or_404(
        Project.objects.select_related('category').prefetch_related(
            'images',
            'field_values__field',
        ),
        slug=slug,
    )
    return render(request, 'projects/project_detail.html', {'project': project})


def about(request):
    return render(request, 'projects/about.html')


def services(request):
    return render(request, 'projects/services.html')


@ratelimit(key='ip', rate='5/h', block=True)
def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            enquiry = form.save()
            send_mail(
                subject=f'New enquiry from {enquiry.name}',
                message=(
                    f'Name: {enquiry.name}\n'
                    f'Email: {enquiry.email}\n'
                    f'Project type: {enquiry.project_type or "Not specified"}\n\n'
                    f'{enquiry.message}'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.ADMIN_EMAIL],
                fail_silently=True,
            )
            messages.success(request, "Thank you. We'll be in touch shortly.")
            return redirect('projects:contact')
    else:
        form = ContactForm()
    return render(request, 'projects/contact.html', {'form': form})


def handler404(request, exception):
    return render(request, 'projects/404.html', status=404)


def handler500(request):
    return render(request, 'projects/500.html', status=500)
