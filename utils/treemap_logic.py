from PyQt6.QtCore import QRectF

class TreeMapItem:
    def __init__(self, name, value, item_type="process", data=None):
        self.name = name
        self.value = value
        self.type = item_type
        self.data = data or {}
        self.rect = QRectF(0, 0, 0, 0)
        self.children = [] # 如果有子节点，则它是分组

    def formatted_size(self):
        val = self.value
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if val < 1024.0:
                return f"{val:.2f} {unit}"
            val /= 1024.0
        return f"{val:.2f} PB"

def squarify_layout(items, x, y, width, height):
    """
    对一组 items 进行 squarify 布局计算。
    """
    # 过滤掉 value 为 0 的项，避免后续计算出现除以零错误
    valid_items = [i for i in items if i.value > 0]
    
    if not valid_items or width <= 0 or height <= 0:
        return []

    total_value = sum(item.value for item in valid_items)
    if total_value == 0: return []

    # 归一化：将 value 映射到面积
    total_area = width * height
    for item in valid_items:
        item.area = (item.value / total_value) * total_area

    result_items = []
    _squarify_recursive(sorted(valid_items, key=lambda x: x.area, reverse=True), [], x, y, width, height, result_items)
    return result_items

def _squarify_recursive(children, row, x, y, width, height, result):
    if not children:
        _layout_row(row, x, y, width, height, result)
        return

    child = children[0]
    side = min(width, height)
    
    if not row:
        _squarify_recursive(children[1:], [child], x, y, width, height, result)
    else:
        current_worst = _worst(row, side)
        next_worst = _worst(row + [child], side)
        
        if current_worst >= next_worst:
            _squarify_recursive(children[1:], row + [child], x, y, width, height, result)
        else:
            _layout_row(row, x, y, width, height, result)
            row_area = sum(n.area for n in row)
            if width < height:
                # 垂直剩余
                h_used = row_area / width
                _squarify_recursive(children, [], x, y + h_used, width, height - h_used, result)
            else:
                # 水平剩余
                w_used = row_area / height
                _squarify_recursive(children, [], x + w_used, y, width - w_used, height, result)

def _worst(row, side):
    if not row or side == 0: return float('inf')
    row_area = sum(n.area for n in row)
    if row_area == 0: return float('inf')
    
    max_area = max(n.area for n in row)
    min_area = min(n.area for n in row)
    
    if min_area == 0: return float('inf')
    
    return max((side**2 * max_area) / (row_area**2), (row_area**2) / (side**2 * min_area))

def _layout_row(row, x, y, width, height, result):
    if not row: return
    row_area = sum(n.area for n in row)
    if width < height:
        row_height = row_area / width if width > 0 else 0
        curr_x = x
        for node in row:
            w = node.area / row_height if row_height > 0 else 0
            node.rect = QRectF(curr_x, y, w, row_height)
            curr_x += w
            result.append(node)
    else:
        row_width = row_area / height if height > 0 else 0
        curr_y = y
        for node in row:
            h = node.area / row_width if row_width > 0 else 0
            node.rect = QRectF(x, curr_y, row_width, h)
            curr_y += h
            result.append(node)

