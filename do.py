import os
import re
import yaml
import json
from datetime import datetime
import argparse
import frontmatter
import markdown
import shutil
from jinja2 import Environment, FileSystemLoader, select_autoescape
from dataclasses import dataclass, field, asdict, replace
from typing import List, Dict, Any, Optional
from operator import attrgetter 

# Define a constant for default template directory
DEFAULT_TEMPLATE_DIR = 'templates'  # Adjust to your default template directory path
MARKDOWN_EXTENSIONS = ['tables', 'toc']

# Setting up Jinja2 environment
def setup_jinja_env(template_dir):
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape()
    )
    return env

@dataclass(frozen=True)
class GroupConfig:
    name: str
    template: str
    path_config: List[str]
    rss: Any

    def get_template(self, env):
        return env.get_template(self.template)

    def make_path_for_file(self, info: Dict[str, Any]) -> str:
        parts = []
        for field_level in self.path_config:
            fields_in_level = field_level.split("+")
            resolved_fields_in_level = map(lambda f: GroupConfig._resolve_path_field(f, info), fields_in_level)
            resolved_level = "".join(resolved_fields_in_level)
            parts.append(resolved_level)
        path_str = '/' + '/'.join(parts)
        path_str = re.sub(r'/+', '/', path_str)
        # TODO: Remove.
        if len(path_str)>1: 
            path_str += '.html'
        return path_str

    def _resolve_path_field(field: str, info: Dict[str, Any]):
        if field.startswith("\"") and field.endswith("\""):
            return str(eval(field))
        else:
            return str(eval(f'info{field}'))


@dataclass(frozen=True)
class Config:
    formats: Dict[str, Any]
    groups: List[GroupConfig]
    title: str
    favicon: str

    @classmethod
    def load_from_yaml(cls, path: str) -> 'Config':
        with open(path, 'r') as f:
            y = yaml.safe_load(f)
            groups = [GroupConfig(**gc) for gc in y['groups']]
            formats = y['formats']
            title = y["title"]
            # TODO: Add file / url support.
            print("ZOR", y)
            if favicon_emoji := y["favicon"].get("emoji", None):
                favicon = f"https://emoji.dutl.uk/png/128x128/{favicon_emoji}.png"
            else:
                favicon = ""
            return cls(formats=formats, groups=groups, title=title, favicon=favicon)


@dataclass(frozen=True)
class FileContext:
    extension: str
    out_extension: str
    file_path: str
    file_relpath: str
    file_relpath_without_extension: str
    meta: Dict[str, Any]
    content: str
    content_html: str
    preview_html: str
    group: Optional[GroupConfig] = field(default=None, repr=False)
    calculated_uri: str = ''


def get_file_extension(file_path: str) -> str:
    return os.path.splitext(file_path)[1][1:]


def get_filepath_without_extension(file_path: str) -> str:
    return os.path.splitext(file_path)[0][:]


def parse_markdown(file_path: str) -> Dict[str, Any]:
    with open(file_path, 'r', encoding='utf-8') as f:
        post = frontmatter.load(f)
        preview_content = post_to_preview_md(post.content)
        content_html = markdown.markdown(post.content, extensions=MARKDOWN_EXTENSIONS)
        preview_html = markdown.markdown(preview_content, extensions=MARKDOWN_EXTENSIONS)
        return {
            'meta': post.metadata,
            'content': post.content,
            'content_html': content_html,
            'preview_html': preview_html,
        }

def post_to_preview_md(md: str):
    preview_content = re.sub("# ", "## ", md)
    preview_content = "\n\n".join(preview_content.split("\n\n")[:10])
    return preview_content


def parse_config(path: str) -> Config:
    return Config.load_from_yaml(path)


def prepare_out_dir(out_dir: str):
    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir, exist_ok=True)


def resolve_groups(file_contexts: List[FileContext], config: Config) -> List[FileContext]:
    group_dict = {group.name: group for group in config.groups}
    return [
        replace(file_context, group=group_dict[file_context.meta['group']])
        for file_context in file_contexts
    ]


def make_paths(file_contexts: List[FileContext]) -> List[FileContext]:
    return [
        replace(file_context, calculated_uri=file_context.group.make_path_for_file(asdict(file_context)))
        for file_context in file_contexts
    ]


def write_files(file_contexts: List[FileContext], out_dir: str, config: Dict):
    context_dicts = [asdict(context_item) for context_item in file_contexts]
    tags = [item for list_ in [context_item.meta.get("tags", []) for context_item in file_contexts] for item in list_]
    references = {
        context["meta"]["reference"]: context 
        for context in context_dicts if context["meta"].get("reference", None)
    }
    for context in file_contexts:
        uri_slash_filename = context.calculated_uri.lstrip('/')
        if not uri_slash_filename:
            uri_slash_filename = 'index.html'
        else:
            uri_slash_filename += f".{context.out_extension}"
        # TODO: Remove.
        uri_slash_filename = re.sub("(\.html)+", ".html", uri_slash_filename)
        out_path = os.path.join(out_dir, uri_slash_filename).rstrip('/')
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'w') as f:
            render = context.group.get_template(env).render(
                context=asdict(context), 
                all=context_dicts, 
                tags=tags, 
                references=references,
                config=config,
            )
            print("RENDER:", render)
            f.write(render)


def generate_rss(file_contexts: List[FileContext], out_dir: str, site_url: str):
    site_url = site_url.rstrip('/')
    group_names_with_rss = {fc.group.name for fc in file_contexts if fc.group and fc.group.rss}
    group_contexts = [fc for fc in file_contexts if fc.group and fc.group.name in group_names_with_rss]
    if not group_contexts:
        return
    rss_template = env.get_template('rss.xml.j2')
    rss_content = rss_template.render(group=group_contexts[0].group, file_contexts=group_contexts, site_url=site_url)
    rss_path = os.path.join(out_dir, "rss.xml")
    with open(rss_path, 'w', encoding='utf-8') as rss_file:
        rss_file.write(rss_content)



def parse_directory(src_dir: str, ext_whitelist: List[str]) -> List[FileContext]:
    file_contexts = []
    for root, _, files in os.walk(src_dir):
        for file in files:
            file_path = os.path.join(root, file)
            file_relpath = os.path.relpath(file_path, start=src_dir)
            extension = get_file_extension(file_path)
            if extension not in ext_whitelist:
                continue
            parsed_data = parse_markdown(file_path)
            file_contexts.append(FileContext(
                extension=extension,
                out_extension='html',
                file_path=file_path,
                file_relpath=file_relpath,
                file_relpath_without_extension=get_filepath_without_extension(file_relpath),
                **parsed_data
            ))
    return file_contexts


def main(src_dir: str, out_dir: str, config_relpath: str, site_url: str, template_dir: str):
    global env
    env = setup_jinja_env(template_dir)
    
    config_path = os.path.join(src_dir, config_relpath)
    config = parse_config(config_path)
    prepare_out_dir(out_dir)
    file_contexts = parse_directory(src_dir, ['md'])
    file_contexts = resolve_groups(file_contexts, config)
    file_contexts = make_paths(file_contexts)
    # print(json.dumps([asdict(context) for context in file_contexts], indent=2, default=str))
    write_files(file_contexts, out_dir, config)
    generate_rss(file_contexts, out_dir, site_url)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process some files.')
    parser.add_argument('--src_dir', type=str, required=True, help='Source directory containing markdown files')
    parser.add_argument('--out_dir', type=str, required=True, help='Output directory for generated files')
    parser.add_argument('--config_relpath', type=str, required=False, default='config.yaml', help='Path to configuration YAML file')
    parser.add_argument('--site_url', type=str, required=True, help='Base URL of the site')
    parser.add_argument('--template_dir', type=str, required=False, default=DEFAULT_TEMPLATE_DIR, help='Path to directory containing Jinja templates')
    
    args = parser.parse_args()
    
    main(src_dir=args.src_dir, out_dir=args.out_dir, config_relpath=args.config_relpath, site_url=args.site_url, template_dir=args.template_dir)
