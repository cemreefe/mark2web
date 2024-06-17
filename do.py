import os
import re
import yaml
import json
from datetime import datetime
import frontmatter
import markdown
import shutil
from jinja2 import Environment, PackageLoader, select_autoescape

env = Environment(
    loader=PackageLoader("do"),
    autoescape=select_autoescape()
)
class Config:

    class Group:

        INSTANCES = {}

        def __init__(self, name, template, path_config, rss):
            self.name = name
            self.template_ = template
            self.template = env.get_template(template)
            self.path_config = path_config
            self.rss = rss
            Config.Group.INSTANCES[name] = self

        @classmethod
        def get_group_by_name(cls, name):
            return Config.Group.INSTANCES.get(name, None)

        def make_path_for_file(self, info):
            parts = []
            for field in self.path_config:
                if field.startswith("\"") and field.endswith("\""):
                    parts.append(str(eval(field)))
                else:
                    parts.append(str(eval('info' + field)))
            path_str = '/'.join(parts)
            path_str = re.sub(r'/+', '/', path_str)            
            return path_str



    def __init__(self, formats = None, groups = None):
        self.formats = formats
        self.groups = groups

    @classmethod
    def load_from_yaml(cls, path):
        with open(path, 'r') as f:
            y = yaml.safe_load(f)
            formats = y['formats']
            groups = [Config.Group(**gc) for gc in y['groups']]
            return cls(formats=formats, groups=groups)

class Parser:

    EXTENSIONS_WHITELIST = ['md']
    CONFIG_FILE = 'config.yaml'

    def __init__(self, src_dir, out_dir):
        self.src_dir = src_dir
        self.out_dir = out_dir
        self.dictionary = {}
        # self.expanded_meta = {}
        self.config = None

    def prepare_out_dir(self):
        shutil.rmtree(self.out_dir)
        os.makedirs(self.out_dir, exist_ok=True)

    def parse_config(self):
        self.config = Config.load_from_yaml(self.CONFIG_FILE)

    @classmethod
    def get_file_extension(cls, file_path):
        return os.path.splitext(file_path)[1][1:]

    @classmethod
    def get_filepath_without_extension(cls, file_path):
        return os.path.splitext(file_path)[0][:]

    @classmethod
    def parse_markdown(cls, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            post = frontmatter.load(f)
            meta = post.metadata
            content = post.content
            content_html = markdown.markdown(content)  # Render the markdown content to HTML
            
            return {
                'meta': meta,
                'content': content,
                'content_html': content_html
            }


    @classmethod
    def get_parser(cls, extension):
        PARSERS = {
            'md': Parser.parse_markdown,
        }
        return_null = lambda path: None
        return PARSERS.get(extension, return_null)

    def parse_directory(self):
        for root, _, files in os.walk(self.src_dir):
            for file in files:
                file_path = os.path.join(root, file)
                file_relpath = os.path.relpath(file_path, start=self.src_dir)
                extension = Parser.get_file_extension(file_path)
                path_without_extension = Parser.get_filepath_without_extension(file_path)
                if extension not in self.EXTENSIONS_WHITELIST:
                    continue
                _parser = Parser.get_parser(extension)
                print("_parser:", _parser(file_path))
                self.dictionary[file_path] = {
                    'extension': extension,
                    'out_extension': 'html',
                    'file_path': file_path,
                    'file_relpath': file_relpath,
                    'file_relpath_without_extension': path_without_extension,
                    **_parser(file_path),
                }

    def resolve_groups(self):
        for file_path in self.dictionary:
            group_name = self.dictionary[file_path]['meta']['group']
            group = Config.Group.get_group_by_name(group_name)
            self.dictionary[file_path]['group'] = group

    def make_paths(self):
        for file_path, context in self.dictionary.items():
            path = context['group'].make_path_for_file(self.dictionary[file_path])
            self.dictionary[file_path]['calculated_uri'] = path

    def write(self):
        for _, context in self.dictionary.items():
            uri_slash_filename = context['calculated_uri'].lstrip('/')
            uri_slash_filename = uri_slash_filename + "." + context['out_extension'] if uri_slash_filename else 'index.html'
            out_path = os.path.join(self.out_dir, uri_slash_filename).rstrip('/')
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, 'w') as f:
                render = context['group'].template.render(context=context)
                f.write(render)

    def make(self):
        self.parse_config()
        self.prepare_out_dir()
        self.parse_directory()
        self.resolve_groups()
        self.make_paths()

        print(json.dumps(self.dictionary, indent=2, default=str))

        self.write()

    
    def process_groups():
        pass

# Example usage
parser = Parser(
    src_dir='test_folder',
    out_dir='test_output',
)

parser.make()

# for file_path, data in markdown_files.items():
