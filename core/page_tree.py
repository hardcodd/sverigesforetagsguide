"""Build navigation trees from a single materialized-path page query."""

from collections.abc import Iterable
from dataclasses import dataclass, field

from wagtail.models import Page


@dataclass
class PageTreeNode:
    """Expose the page and its already-loaded children to navigation templates."""

    page: Page
    children: list["PageTreeNode"] = field(default_factory=list)

    @property
    def title(self) -> str:
        return self.page.title

    @property
    def url(self) -> str | None:
        return self.page.url


def build_page_tree(pages: Iterable[Page], parent: Page) -> list[PageTreeNode]:
    """Preserve input order and omit branches whose parents are not included.

    Wagtail's materialized paths encode the parent by removing one step. The
    caller selects visible pages; no additional database queries run per node.
    """
    nodes = {str(page.path): PageTreeNode(page) for page in pages}
    roots: list[PageTreeNode] = []
    for path, node in nodes.items():
        parent_path = path[: -Page.steplen]
        if parent_path == parent.path:
            roots.append(node)
        elif parent_path in nodes:
            nodes[parent_path].children.append(node)
    return roots
