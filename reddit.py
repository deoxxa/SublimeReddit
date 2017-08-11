import datetime
import json
import sublime
import sublime_plugin
import textwrap
import urllib.request


def find_or_make_view(window, **kwargs):
    for view in window.views():
        s = view.settings()
        matches = [s.get(k) == v for k, v in list(kwargs.items())]
        if all(matches):
            return view
    view = window.new_file()
    for k, v in list(kwargs.items()):
        view.settings().set(k, v)
    return view


def unescape(s):
    return s.replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&')


def wrap(s, indent="", width=80):
    return textwrap.indent('\n'.join(map(lambda l: textwrap.fill(textwrap.dedent(l), width=width), s.split('\n'))), indent)


class RedditBaseCommand(sublime_plugin.TextCommand):

    def is_visible(self):
        return False

    def draw_item(self, edit, view, item, indent):
        if item.get('kind') == 't1':
            return self.draw_t1(edit, view, item.get('data', {}), indent)
        if item.get('kind') == 't3':
            return self.draw_t3(edit, view, item.get('data', {}), indent)
        return ''

    def draw_t1(self, edit, view, item, indent):
        created = item.get('created_utc', None)
        if created is not None:
            created = datetime.datetime.fromtimestamp(
                created).strftime('%A, %d. %B %Y %I:%M%p')

        title_start = view.size()
        view.insert(edit, view.size(), '%s# [%d] [%s] %s' % (
            indent[2:], item.get('score', 0), item.get('author', ''), created))
        title_end = view.size()
        view.insert(edit, view.size(), '\n\n')
        view.add_regions(
            'thread-%s-title' % (item.get('id', '')),
            [sublime.Region(title_start, title_end)],
            'thread-title',
            'dot',
            flags=sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE | sublime.DRAW_SOLID_UNDERLINE
        )

        content = wrap(unescape(item.get('body', '')).strip(), indent)

        content_start = view.size()
        view.insert(edit, view.size(), content)
        content_end = view.size() - 1
        view.insert(edit, view.size(), '\n\n')
        view.add_regions(
            'thread-%s-body' % item.get('id', ''),
            [sublime.Region(content_start, content_end)],
            'thread-body',
            flags=sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE | sublime.HIDE_ON_MINIMAP
        )

        replies = item.get('replies', {})
        if isinstance(replies, dict):
            for child in replies.get('data', {}).get('children', []):
                self.draw_item(edit, view, child, indent + '  ')

    def draw_t3(self, edit, view, item, indent):
        title_start = view.size()
        view.insert(edit, view.size(), '# [%s] [%5d] %s' % (
            item.get('id', ''), item.get('score', 0), item.get('title', '???')))
        title_end = view.size()
        view.insert(edit, view.size(), '\n\n')
        view.add_regions(
            'thread-%s-title' % (item.get('id', '')),
            [sublime.Region(title_start, title_end)],
            'thread-title',
            'bookmark',
            flags=sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE | sublime.DRAW_SOLID_UNDERLINE
        )

        content = wrap(unescape(item.get('selftext', '')).strip(), indent)

        content_start = view.size()
        view.insert(edit, view.size(), content)
        content_end = view.size() - 1
        view.insert(edit, view.size(), '\n\n')
        view.add_regions(
            'thread-%s-body' % item.get('id', ''),
            [sublime.Region(content_start, content_end)],
            'thread-body',
            flags=sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE | sublime.HIDE_ON_MINIMAP
        )


class RedditBrowseSubredditCommand(RedditBaseCommand):

    def is_visible(self):
        return True

    def run(self, edit):
        for region in self.view.sel():
            to_open = self.view.substr(region).lower()

            view = find_or_make_view(
                self.view.window(), reddit_view='subreddit', reddit_subreddit=to_open)
            view.set_name('%s (loading)' % (to_open))
            view.set_scratch(True)

            view.window().focus_view(view)

            req = urllib.request.Request('https://www.reddit.com/r/%s.json' % (to_open), data=None, headers={
                'User-Agent': 'SublimeText-Reddit/0.1',
            })

            page = json.loads(urllib.request.urlopen(
                req).read().decode('utf-8'))

            view.set_name(to_open)

            view.set_read_only(False)
            view.erase(edit, sublime.Region(0, view.size()))
            for item in page.get('data', {}).get('children', []):
                self.draw_item(edit, view, item, '')
            view.set_read_only(True)


class RedditViewThreadCommand(RedditBaseCommand):

    def is_visible(self):
        return True

    def run(self, edit):
        for region in self.view.sel():
            to_open = self.view.substr(region).lower()

            view = find_or_make_view(
                self.view.window(), reddit_view='thread', reddit_thread=to_open)
            view.set_name('%s (loading)' % (to_open))
            view.set_scratch(True)

            view.window().focus_view(view)

            req = urllib.request.Request('https://www.reddit.com/comments/%s.json' % (to_open), data=None, headers={
                'User-Agent': 'SublimeText-Reddit/0.1',
            })

            page = json.loads(urllib.request.urlopen(
                req).read().decode('utf-8'))

            title = page[0]['data']['children'][0]['data']['title']

            view.set_name(title)

            view.set_read_only(False)
            view.erase(edit, sublime.Region(0, view.size()))
            self.draw_item(edit, view, page[0]['data']['children'][0], '')
            for item in page[1]['data']['children']:
                self.draw_item(edit, view, item, '  ')
            view.set_read_only(True)
