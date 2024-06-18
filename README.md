# Mark2Web

This project is a simple static site generator written in Python. It reads Markdown files from a source directory, processes them according to a specified configuration, and outputs HTML files to a target directory.

## Features

- Converts Markdown files to HTML.
- Supports front matter for metadata in Markdown files.
- Organizes output files based on metadata and configuration.
- Uses Jinja2 for templating.
- Fully customizable™️

## Requirements

- Python 3.7 or higher
- PyYAML
- Python Frontmatter
- Markdown
- Jinja2

## Installation

1. Clone the repository:

    ```sh
    git clone https://github.com/yourusername/static-site-generator.git
    cd static-site-generator
    ```

2. Install the required packages:

    ```sh
    pip install -r requirements.txt
    ```

## Configuration

The configuration file `config.yaml` specifies how the files should be processed. It includes format settings and group configurations. Below is an example configuration:

```yaml
formats:
  meta.date: '%Y-%m-%d'
groups:
  - name: post
    template: blog_template.html
    rss: true
    path_config:
      - "\"p\""
      - "['meta']['date'].year"
      - "['meta']['handle']"
  - name: default
    template: generic.html
    rss: false
    path_config:
      - "['meta']['canonical-url']"
```

## Usage

1. Create a source directory with Markdown files. Each Markdown file should have front matter metadata. For example:

    ```markdown
    ---
    title: "My First Blog Post"
    date: 2024-06-18
    group: "blog"
    slug: "my-first-blog-post"
    ---

    # My First Blog Post

    This is the content of my first blog post.
    ```

2. Create the necessary Jinja2 templates in the `templates` directory. For example, `blog_template.html` might look like this:

    ```html
    <!DOCTYPE html>
    <html>
    <head>
        <title>{{ context.meta.title }}</title>
    </head>
    <body>
        <h1>{{ context.meta.title }}</h1>
        <div>{{ context.content_html | safe }}</div>
    </body>
    </html>
    ```

    Check out `test_folder` and `test_output` for more complete examples.

3. Run the  script with the source directory, output directory, and configuration file:

    ```sh
    python do.py
    ```

## Contributing

Contributions are welcome! Please open an issue or submit a pull request on GitHub.

## Contact

For questions or suggestions, please contact [cemrekr@aol.com](mailto:cemrekr@aol.com).