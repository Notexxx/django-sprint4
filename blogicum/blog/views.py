from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .forms import CommentForm, PostForm, ProfileForm
from .models import Category, Comment, Post

POSTS_PER_PAGE = 10


def _published_conditions():
    return Q(
        is_published=True,
        category__is_published=True,
        pub_date__lte=timezone.now(),
    )


def _paginate_posts(request, posts):
    posts = (
        posts.select_related('author', 'category', 'location')
        .annotate(comment_count=Count('comments'))
        .order_by('-pub_date', '-pk')
    )
    return Paginator(posts, POSTS_PER_PAGE).get_page(request.GET.get('page'))


def _visible_post(user, post_id):
    conditions = _published_conditions()
    if user.is_authenticated:
        conditions |= Q(author=user)
    posts = Post.objects.select_related('author', 'category', 'location')
    return get_object_or_404(posts.filter(conditions), pk=post_id)


def index(request):
    posts = Post.objects.filter(_published_conditions())
    return render(request, 'blog/index.html', {
        'page_obj': _paginate_posts(request, posts),
    })


def _render_post_detail(request, post, form):
    return render(request, 'blog/detail.html', {
        'post': post,
        'form': form,
        'comments': post.comments.select_related('author'),
    })


def post_detail(request, id):
    return _render_post_detail(
        request, _visible_post(request.user, id), CommentForm(),
    )


def category_posts(request, category_slug):
    category = get_object_or_404(
        Category, slug=category_slug, is_published=True,
    )
    posts = category.posts.filter(_published_conditions())
    return render(request, 'blog/category.html', {
        'category': category,
        'page_obj': _paginate_posts(request, posts),
    })


def profile(request, username):
    profile_user = get_object_or_404(get_user_model(), username=username)
    posts = profile_user.posts.all()
    if request.user != profile_user:
        posts = posts.filter(_published_conditions())
    return render(request, 'blog/profile.html', {
        'profile': profile_user,
        'page_obj': _paginate_posts(request, posts),
    })


@login_required
@require_http_methods(('GET', 'HEAD', 'POST'))
def edit_profile(request):
    data = request.POST if request.method == 'POST' else None
    form = ProfileForm(data, instance=request.user)
    if form.is_valid():
        profile_user = form.save()
        return redirect('blog:profile', profile_user.username)
    return render(request, 'blog/user.html', {'form': form})


@login_required
@require_http_methods(('GET', 'HEAD', 'POST'))
def create_post(request):
    form = PostForm()
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            return redirect('blog:profile', request.user.username)
    return render(request, 'blog/create.html', {'form': form})


@login_required
@require_http_methods(('GET', 'HEAD', 'POST'))
def edit_post(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if post.author_id != request.user.pk:
        return redirect('blog:post_detail', post_id)
    form = PostForm(instance=post)
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            return redirect('blog:post_detail', post_id)
    return render(request, 'blog/create.html', {'form': form})


@login_required
@require_http_methods(('GET', 'HEAD', 'POST'))
def delete_post(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if post.author_id != request.user.pk:
        return redirect('blog:post_detail', post_id)
    if request.method == 'POST':
        post.delete()
        return redirect('blog:index')
    return render(request, 'blog/create.html', {
        'form': PostForm(instance=post),
    })


@login_required
@require_POST
def add_comment(request, post_id):
    post = _visible_post(request.user, post_id)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        comment.save()
        return redirect('blog:post_detail', post_id)
    return _render_post_detail(request, post, form)


def _post_comment(request, post_id, comment_id):
    post = _visible_post(request.user, post_id)
    return get_object_or_404(Comment, post=post, pk=comment_id)


@login_required
@require_http_methods(('GET', 'HEAD', 'POST'))
def edit_comment(request, post_id, comment_id):
    comment = _post_comment(request, post_id, comment_id)
    if comment.author_id != request.user.pk:
        return redirect('blog:post_detail', post_id)
    data = request.POST if request.method == 'POST' else None
    form = CommentForm(data, instance=comment)
    if form.is_valid():
        form.save()
        return redirect('blog:post_detail', post_id)
    return render(request, 'blog/comment.html', {
        'comment': comment,
        'form': form,
    })


@login_required
@require_http_methods(('GET', 'HEAD', 'POST'))
def delete_comment(request, post_id, comment_id):
    comment = _post_comment(request, post_id, comment_id)
    if comment.author_id != request.user.pk:
        return redirect('blog:post_detail', post_id)
    if request.method == 'POST':
        comment.delete()
        return redirect('blog:post_detail', post_id)
    return render(request, 'blog/comment.html', {'comment': comment})
