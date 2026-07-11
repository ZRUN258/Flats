import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
# from mpl_toolkits.mplot3d import Axes3D # 如果不需要3D可以注释掉

class MyFigureCanvas(FigureCanvas):
    def __init__(self, my_parent=None, width=6, height=6, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super(MyFigureCanvas, self).__init__(self.fig)
        
        # 初始化第一个坐标轴
        self.ax = self.fig.add_subplot(111)
        self._set_default_limits()

        # 测试数据 (保留你的代码)
        self.x = np.arange(-4, 4, 0.02)
        self.y = np.arange(-4, 4, 0.02)
        self.X, self.Y = np.meshgrid(self.x, self.y)
        self.z = np.sin(self.x)
        self.R = np.sqrt(self.X ** 2 + self.Y ** 2)
        self.Z = np.sin(self.R)

    def _set_default_limits(self):
        """设置默认的坐标轴范围和样式"""
        self.ax.set_title("2D track map, unit: mm")
        self.ax.set_xlim(-0.001, 0.005)
        self.ax.set_ylim(-0.001, 0.005)
        self.ax.set_aspect(1) # 保证X和Y轴比例一致，圆不会变成椭圆
        self.ax.grid(True, linestyle='--', alpha=0.5) # 加个网格好看点

    def track_test(self):
        """测试函数"""
        self.ax.cla() # 清空
        self._set_default_limits() # 重置样式
        
        x = [0, 0.1, 0.2, 0.3, 0.4, 0.5] # 简化测试数据
        y = [0] * len(x)
        self.ax.plot(x, y)
        self.draw()

    def draw_track(self, x, y, add_point=True):
        """
        绘制实时轨迹点
        :param x: X 坐标列表 (List[float])
        :param y: Y 坐标列表 (List[float])
        :param add_point: 是否显示每一个物理采样点
        """
        # 1. 基础检查：确保有数据且长度匹配
        if not x or not y or len(x) != len(y):
            return

        # 2. 清空当前坐标轴，准备重绘
        # 对于实时绘图，cla() 虽然简单粗暴，但能有效防止旧图层堆叠导致的内存泄漏
        self.ax.cla()

        # 3. 绘制轨迹线 (Path)
        # zorder 决定层级，数值越大越靠上
        self.ax.plot(x, y, color='blue', linestyle='-', linewidth=1.5, label='Trajectory', zorder=1)

        # 4. 绘制采样点 (Optional)
        if add_point:
            # 使用点状标记 'o'，不连线
            self.ax.plot(x, y, 'o', color='orange', markersize=3, alpha=0.6, label='Nodes', zorder=2)

        # 5. 突出显示当前位置 (最新点)
        # 使用五角星 'p' 或大圆点，红色醒目
        self.ax.plot(x[-1], y[-1], marker='p', color='red', markersize=10, 
                     markeredgecolor='white', label='Current', zorder=3)

        # 6. 【核心】自适应坐标轴与比例控制
        # 这一步修复了你坐标轴停留在 0.005 的问题
        self.ax.relim()           # 重新计算数据极限
        self.ax.autoscale_view()  # 自动调整视图范围
        
        # 强制 1:1 比例，防止圆弧被压扁成椭圆
        self.ax.set_aspect('equal', adjustable='box')

        # 7. 界面装饰
        self.ax.set_title(f"Real-time Tracking (Latest: {x[-1]:.2f}, {y[-1]:.2f})", fontsize=10)
        self.ax.set_xlabel('X Axis (mm)')
        self.ax.set_ylabel('Y Axis (mm)')
        self.ax.grid(True, linestyle='--', alpha=0.5)
        
        # 只有在点比较多的时候显示图例，避免遮挡
        if len(x) > 1:
            self.ax.legend(loc='upper right', fontsize='x-small', framealpha=0.5)

        # 8. 刷新画布
        # 使用 draw_idle 相比 draw 性能更好，它会在 GUI 空闲时重绘，避免界面卡死
        self.draw_idle()
    # 下面是你原来的其他绘图函数，保持不动即可
    def draw_line(self):
        self.ax.cla() # 改用 cla
        self.ax.set_xlim(-4, 4)
        self.ax.set_ylim(-1, 1)
        self.line = Line2D(self.x, self.z)
        self.ax.add_line(self.line)
        self.draw()

    def draw_bar(self):
        self.ax.cla() # 改用 cla
        self.ax.set_xlim(-4, 4)
        self.ax.set_ylim(-1, 1)
        self.bar = self.ax.bar(np.arange(-4, 4, 0.5), np.sin(np.arange(-4, 4, 0.5)), width=0.4)
        self.draw()

    def draw_img(self):
        self.ax.cla() # 改用 cla
        self.img = self.ax.imshow(self.Z, cmap='bone')
        self.img.set_clim(-0.8, 0.8)
        self.draw()

    def draw_surface(self):
        # 3D绘图比较特殊，需要重新添加 projection
        self.ax.cla() 
        from mpl_toolkits.mplot3d import Axes3D # 局部导入
        self.ax = self.fig.add_subplot(111, projection='3d')
        self.surf = self.ax.plot_surface(self.X, self.Y, self.Z, cmap='rainbow')
        self.draw()