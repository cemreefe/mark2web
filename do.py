import os
import re
import yaml
import json
from datetime import datetime
import frontmatter
import markdown
import shutil
from jinja2 import Environment, PackageLoader, select_autoescape
from dataclasses import dataclass, field, asdict, replace
from typing import List, Dict, Any, Optional

# Setting up Jinja2 environment
env = Environment(
    loader=PackageLoader("do"),
    autoescape=select_autoescape()
)

@dataclass(frozen=True)
class GroupConfig:
    name: str
    template: str
    path_config: List[str]
    rss: Any

    def get_template(self):
        return env.get_template(self.template)

    def make_path_for_file(self, info: Dict[str, Any]) -> str:
        parts = []
        for field in self.path_config:
            if field.startswith("\"") and field.endswith("\""):
                parts.append(str(eval(field)))
            else:
                parts.append(str(eval(f'info{field}')))
        path_str = '/'.join(parts)
        path_str = re.sub(r'/+', '/', path_str)
        return path_str


@dataclass(frozen=True)
class Config:
    formats: Dict[str, Any]
    groups: List[GroupConfig]

    @classmethod
    def load_from_yaml(cls, path: str) -> 'Config':
        with open(path, 'r') as f:
            y = yaml.safe_load(f)
            groups = [GroupConfig(**gc) for gc in y['groups']]
            return cls(formats=y['formats'], groups=groups)


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
    group: Optional[GroupConfig] = field(default=None, repr=False)
    calculated_uri: str = ''


def get_file_extension(file_path: str) -> str:
    return os.path.splitext(file_path)[1][1:]


def get_filepath_without_extension(file_path: str) -> str:
    return os.path.splitext(file_path)[0][:]


def parse_markdown(file_path: str) -> Dict[str, Any]:
    with open(file_path, 'r', encoding='utf-8') as f:
        post = frontmatter.load(f)
        content_html = markdown.markdown(post.content)
        return {
            'meta': post.metadata,
            'content': post.content,
            'content_html': content_html
        }


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


def write_files(file_contexts: List[FileContext], out_dir: str):
    context_dicts = [asdict(context_item) for context_item in file_contexts]
    for context in file_contexts:
        uri_slash_filename = context.calculated_uri.lstrip('/')
        if not uri_slash_filename:
            uri_slash_filename = 'index.html'
        else:
            uri_slash_filename += f".{context.out_extension}"
        out_path = os.path.join(out_dir, uri_slash_filename).rstrip('/')
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'w') as f:
            render = context.group.get_template().render(context=asdict(context), all=context_dicts)
            f.write(render)


def parse_directory(src_dir: str, whitelist: List[str]) -> List[FileContext]:
    file_contexts = []
    for root, _, files in os.walk(src_dir):
        for file in files:
            file_path = os.path.join(root, file)
            file_relpath = os.path.relpath(file_path, start=src_dir)
            extension = get_file_extension(file_path)
            if extension not in whitelist:
                continue
            parsed_data = parse_markdown(file_path)
            file_contexts.append(FileContext(
                extension=extension,
                out_extension='html',
                file_path=file_path,
                file_relpath=file_relpath,
                file_relpath_without_extension=get_filepath_without_extension(file_path),
                **parsed_data
            ))
    return file_contexts


def main(src_dir: str, out_dir: str, config_path: str):
    config = parse_config(config_path)
    prepare_out_dir(out_dir)
    file_contexts = parse_directory(src_dir, ['md'])
    file_contexts = resolve_groups(file_contexts, config)
    file_contexts = make_paths(file_contexts)
    print(json.dumps([asdict(context) for context in file_contexts], indent=2, default=str))
    write_files(file_contexts, out_dir)


# Example usage
main(
    src_dir='test_folder',
    out_dir='test_output',
    config_path='config.yaml'
)
