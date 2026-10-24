"""Layered PSD export using the same placement rules as the workbench preview."""

import logging
from pathlib import Path
from tempfile import NamedTemporaryFile

from psd_tools import PSDImage
from psd_tools.constants import Compression, Resource
from psd_tools.psd.image_resources import ImageResource, VersionInfo

from domain.imaging import display_layer, upright
from domain.messages import QT_TRANSLATE_NOOP, Message, Progress, no_progress
from domain.model import Kind, Project

logger = logging.getLogger(__name__)


def export_psd(project: Project, path: Path, progress: Progress = no_progress) -> Path:
    # PSD requires an image-data section; use a compact blank RLE placeholder
    # and explicitly mark it as absent composite data. Editors render the layers.
    # RGBA keeps layer alpha as transparency rather than creating pixel masks.
    psd = PSDImage.new("RGBA", project.size, compression=Compression.RLE)
    psd.image_resources[Resource.VERSION_INFO] = ImageResource(
        key=Resource.VERSION_INFO,
        data=VersionInfo(has_composite=False, writer="Tachie").tobytes(),
    )
    faces = None
    work = [a for a in project.assets if a.kind != Kind.ICON]
    for index, asset in enumerate(work):
        progress(
            Message(QT_TRANSLATE_NOOP("Messages", "Creating layer {0}"), (asset.name,)), index, len(work)
        )
        image, box = display_layer(project, asset)
        left, bottom = box[:2]
        top = project.size[1] - bottom - image.height
        if asset.kind == Kind.FACE and faces is None:
            faces = psd.create_group(name="paintingface")
        parent = faces if asset.kind == Kind.FACE and faces is not None else psd
        name = f"{asset.name} [{asset.texture_name}]" if asset.texture_name else asset.name
        layer = parent.create_pixel_layer(
            upright(image),
            name=f"face #{asset.name}" if asset.kind == Kind.FACE else name,
            top=top,
            left=left,
            # Predictive ZIP preserves every channel while compressing artwork
            # more effectively than PackBits RLE, especially enlarged backgrounds.
            compression=Compression.ZIP_WITH_PREDICTION,
        )
        layer.visible = asset.kind == Kind.PAINTING
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, suffix=".psd.tmp", delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        progress(Message(QT_TRANSLATE_NOOP("Messages", "Writing PSD")), 0, 0)
        with temporary_path.open("wb") as output:
            # save() regenerates a full composite; write the layered record directly.
            info = psd._record.layer_and_mask_information.layer_info
            if info is not None:
                info.layer_count = -abs(info.layer_count)  # channel 4 is transparency
            psd._record.write(output)
        progress(Message(QT_TRANSLATE_NOOP("Messages", "PSD export complete")), 1, 1)
        temporary_path.replace(path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    logger.info("已导出 PSD：%s", path)
    return path
