import sys
import os
import pandas as pd
import sqlite3
import glob
import traceback
from PySide6.QtCore import Qt, QTimer, QSize, Signal
from PySide6.QtGui import QFont, QIcon, QPalette, QColor, QTextDocument
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QRadioButton, QCheckBox, QButtonGroup, QTabWidget,
    QProgressBar, QMessageBox, QFileDialog, QSizePolicy, QTextBrowser,
    QFrame, QListWidget, QListWidgetItem, QAbstractItemView, QComboBox,
    QInputDialog
)
from PySide6.QtPrintSupport import QPrinter


class QuestionManager:
    """题库管理类，负责加载Excel题库和管理题目数据"""

    def __init__(self):
        self.questions = []
        self.current_question_index = 0
        self.question_sets = {}  # 存储多个题库 {题库名称: 题目列表}
        self.current_set = ""  # 当前题库名称
        self.current_file_path = None  # 当前题库文件路径

    def load_from_excel(self, file_path):
        """从Excel文件加载题库"""
        try:
            df = pd.read_excel(file_path)
            required_columns = ['题型', '等级', '题号', '题目编号', '题目内容',
                                '选项A', '选项B', '选项C', '选项D', '正确答案']

            # 验证列名
            if not all(col in df.columns for col in required_columns):
                missing = [col for col in required_columns if col not in df.columns]
                raise ValueError(f"Excel文件缺少必要的列: {', '.join(missing)}")

            # 转换为题目字典列表
            questions = []
            for _, row in df.iterrows():
                question = {
                    'type': row['题型'],
                    'level': row['等级'],
                    'id': row['题号'],
                    'qid': row['题目编号'],
                    'content': row['题目内容'],
                    'options': {
                        'A': row['选项A'],
                        'B': row['选项B'],
                        'C': row['选项C'],
                        'D': row['选项D']
                    },
                    'answer': row['正确答案'],
                    'explanation': row.get('解析', '暂无解析'),
                    'answered': 0,
                    'correct': 0,  # 连续答对次数
                    'wrong': 0,
                    'marked': False,
                    'mastered': False
                }
                questions.append(question)

            # 获取题库名称（使用文件名）
            set_name = os.path.basename(file_path).split('.')[0]
            self.question_sets[set_name] = questions
            self.current_set = set_name
            self.current_file_path = file_path
            return True, f"成功加载 {len(questions)} 道题目"
        except Exception as e:
            return False, f"加载题库失败: {str(e)}"

    def set_current_set(self, set_name):
        """设置当前题库"""
        if set_name in self.question_sets:
            self.current_set = set_name
            self.questions = self.question_sets[set_name]
            self.current_question_index = 0
            return True
        return False

    def get_current_question(self):
        """获取当前题目"""
        if not self.questions:
            return None
        return self.questions[self.current_question_index]

    def next_question(self):
        """移动到下一题（跳过已掌握的题目）"""
        # 找到下一个未掌握的题目
        start_index = self.current_question_index + 1
        for i in range(start_index, len(self.questions)):
            if not self.questions[i]['mastered']:
                self.current_question_index = i
                return True
        return False

    def prev_question(self):
        """移动到上一题（跳过已掌握的题目）"""
        # 找到上一个未掌握的题目
        start_index = self.current_question_index - 1
        for i in range(start_index, -1, -1):
            if not self.questions[i]['mastered']:
                self.current_question_index = i
                return True
        return False

    def prev_question_exists(self):
        """检查是否存在上一题（跳过已掌握的题目）"""
        for i in range(self.current_question_index - 1, -1, -1):
            if not self.questions[i]['mastered']:
                return True
        return False

    def next_question_exists(self):
        """检查是否存在下一题（跳过已掌握的题目）"""
        for i in range(self.current_question_index + 1, len(self.questions)):
            if not self.questions[i]['mastered']:
                return True
        return False

    def record_answer(self, is_correct):
        """记录答题结果"""
        q = self.get_current_question()
        if q:
            q['answered'] += 1
            if is_correct:
                # 增加连续答对次数
                q['correct'] += 1
                print(f"题目 {q['id']} 连续答对次数: {q['correct']}")  # 调试信息

                # 连续答对两次标记为已掌握
                if q['correct'] >= 2 and not q['mastered']:
                    q['mastered'] = True
                    print(f"题目 {q['id']} 标记为已掌握")  # 调试信息
            else:
                # 答错时重置连续答对次数
                q['wrong'] += 1
                q['correct'] = 0
                print(f"题目 {q['id']} 答错，重置连续答对次数")  # 调试信息

    def get_wrong_questions(self):
        """获取所有错题"""
        return [q for q in self.questions if q['wrong'] > 0]

    def get_marked_questions(self):
        """获取所有标记的题目"""
        return [q for q in self.questions if q['marked']]

    def get_progress(self):
        """获取进度信息"""
        total = len(self.questions)
        answered = sum(1 for q in self.questions if q['answered'] > 0)
        correct = sum(1 for q in self.questions if q['correct'] > 0)
        mastered = sum(1 for q in self.questions if q['mastered'])
        unmastered = total - mastered  # 未掌握题数
        return total, answered, correct, mastered, unmastered

    def reset_progress(self, exclude_mastered=True):
        """重置当前题库的进度（除了已掌握的题目）"""
        for q in self.questions:
            if exclude_mastered and q['mastered']:
                continue
            q['answered'] = 0
            # 不要重置连续答对次数 (q['correct'])
            # 不要重置错误次数 (q['wrong'])
            q['marked'] = False
            # 保留连续答对次数、错误次数和已掌握状态

    def release_mastered_questions_by_wrong_count(self, threshold):
        """根据错误次数释放已掌握的题目"""
        count = 0
        for q in self.questions:
            if q['mastered'] and q['wrong'] >= threshold:
                q['mastered'] = False
                q['correct'] = 0  # 重置连续答对次数
                count += 1
        return count


class DatabaseManager:
    """数据库管理类，使用SQLite存储用户数据"""

    def __init__(self, db_path='user_data.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.create_tables()

    def create_tables(self):
        """创建数据库表"""
        cursor = self.conn.cursor()

        # 创建 user_progress 表（如果不存在）
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS user_progress
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           question_id
                           INTEGER,
                           answered
                           INTEGER,
                           correct
                           INTEGER,
                           wrong
                           INTEGER,
                           marked
                           INTEGER,
                           mastered
                           INTEGER,
                           set_name
                           TEXT
                       )
                       ''')

        # 创建 app_state 表（如果不存在）
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS app_state
                       (
                           key
                           TEXT
                           PRIMARY
                           KEY,
                           value
                           TEXT
                       )
                       ''')

        # 检查 user_progress 表是否有 set_name 列
        cursor.execute("PRAGMA table_info(user_progress)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'set_name' not in columns:
            # 添加 set_name 列
            cursor.execute("ALTER TABLE user_progress ADD COLUMN set_name TEXT")

        self.conn.commit()

    def save_progress(self, questions, current_index, set_name):
        """保存当前题库的进度"""
        print(f"保存进度: 题库={set_name}, 位置={current_index}, 题目数={len(questions)}")
        cursor = self.conn.cursor()

        # 清空旧数据
        cursor.execute("DELETE FROM user_progress WHERE set_name=?", (set_name,))
        print(f"已清空旧数据: 题库={set_name}")

        # 插入新数据
        for q in questions:
            cursor.execute('''
                           INSERT INTO user_progress
                               (question_id, answered, correct, wrong, marked, mastered, set_name)
                           VALUES (?, ?, ?, ?, ?, ?, ?)
                           ''', (q['id'], q['answered'], q['correct'], q['wrong'],
                                 int(q['marked']), int(q['mastered']), set_name))
            print(
                f"保存题目进度: ID={q['id']}, 已答={q['answered']}, 正确={q['correct']}, 错误={q['wrong']}, 标记={q['marked']}, 掌握={q['mastered']}")

        # 保存当前位置（为每个题库保存独立的位置）
        cursor.execute('''
            INSERT OR REPLACE INTO app_state (key, value)
            VALUES (?, ?)
        ''', (f'last_position_{set_name}', current_index))
        print(f"保存当前位置: 题库={set_name}, 位置={current_index}")

        # 保存当前题库
        cursor.execute('''
            INSERT OR REPLACE INTO app_state (key, value)
            VALUES ('last_set', ?)
        ''', (set_name,))
        print(f"保存当前题库: {set_name}")

        self.conn.commit()
        print(f"进度保存完成: 题库={set_name}")

    def save_all_progress(self, question_manager):
        """保存所有题库的进度"""
        print(f"保存所有进度: 当前题库={question_manager.current_set}, 位置={question_manager.current_question_index}")
        cursor = self.conn.cursor()

        # 清空所有旧数据
        cursor.execute("DELETE FROM user_progress")
        print("已清空所有旧数据")

        # 插入所有题库的数据
        for set_name, questions in question_manager.question_sets.items():
            for q in questions:
                cursor.execute('''
                               INSERT INTO user_progress
                                   (question_id, answered, correct, wrong, marked, mastered, set_name)
                               VALUES (?, ?, ?, ?, ?, ?, ?)
                               ''', (q['id'], q['answered'], q['correct'], q['wrong'],
                                     int(q['marked']), int(q['mastered']), set_name))
                print(
                    f"保存题目进度: 题库={set_name}, ID={q['id']}, 已答={q['answered']}, 正确={q['correct']}, 错误={q['wrong']}, 标记={q['marked']}, 掌握={q['mastered']}")

        # 保存当前位置
        cursor.execute('''
            INSERT OR REPLACE INTO app_state (key, value)
            VALUES ('last_position', ?)
        ''', (question_manager.current_question_index,))
        print(f"保存当前位置: {question_manager.current_question_index}")

        # 保存当前题库
        cursor.execute('''
            INSERT OR REPLACE INTO app_state (key, value)
            VALUES ('last_set', ?)
        ''', (question_manager.current_set,))
        print(f"保存当前题库: {question_manager.current_set}")

        self.conn.commit()
        print("所有进度保存完成")

    def load_progress(self, set_name):
        """从数据库加载指定题库的进度"""
        print(f"加载进度: 题库={set_name}")
        cursor = self.conn.cursor()

        # 加载题目进度
        cursor.execute(
            "SELECT question_id, answered, correct, wrong, marked, mastered FROM user_progress WHERE set_name=?",
            (set_name,))
        rows = cursor.fetchall()
        print(f"加载到 {len(rows)} 条题目进度记录")

        # 加载该题库的最后位置
        cursor.execute("SELECT value FROM app_state WHERE key=?", (f'last_position_{set_name}',))
        row = cursor.fetchone()
        last_position = int(row[0]) if row else 0
        print(f"加载最后位置: 题库={set_name}, 位置={last_position}")

        # 加载最后题库
        cursor.execute("SELECT value FROM app_state WHERE key='last_set'")
        row = cursor.fetchone()
        last_set = row[0] if row else None
        print(f"加载最后题库: {last_set}")

        return last_position, last_set, rows

    def load_all_progress(self, question_manager):
        """从数据库加载所有题库的进度"""
        print("加载所有进度...")
        cursor = self.conn.cursor()

        # 加载所有题目进度
        cursor.execute("SELECT question_id, answered, correct, wrong, marked, mastered, set_name FROM user_progress")
        rows = cursor.fetchall()
        print(f"加载到 {len(rows)} 条题目进度记录")

        # 加载最后位置
        cursor.execute("SELECT value FROM app_state WHERE key='last_position'")
        row = cursor.fetchone()
        last_position = int(row[0]) if row else 0
        print(f"加载最后位置: {last_position}")

        # 加载最后题库
        cursor.execute("SELECT value FROM app_state WHERE key='last_set'")
        row = cursor.fetchone()
        last_set = row[0] if row else None
        print(f"加载最后题库: {last_set}")

        # 更新所有题库的进度
        for row in rows:
            q_id, answered, correct, wrong, marked, mastered, set_name = row
            if set_name in question_manager.question_sets:
                for q in question_manager.question_sets[set_name]:
                    if q['id'] == q_id:
                        q['answered'] = answered
                        q['correct'] = correct
                        q['wrong'] = wrong
                        q['marked'] = bool(marked)
                        q['mastered'] = bool(mastered)
                        print(
                            f"应用进度: 题库={set_name}, ID={q_id}, 已答={answered}, 正确={correct}, 错误={wrong}, 标记={marked}, 掌握={mastered}")
                        break

        print(f"加载完成: 最后位置={last_position}, 最后题库={last_set}")
        return last_position, last_set


class AnswerWidget(QWidget):
    """答案选项组件"""
    
    # 添加答案选择信号
    answer_selected = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignTop)  # 设置对齐方式为顶部
        self.layout.setSpacing(15)  # 增加选项间距
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.option_widgets = []
        self.is_multiple = False
        self.original_font = QFont("微软雅黑", 25)  # 保存原始字体，增大字体到25号

    def set_question(self, question):
        """根据题目类型设置选项"""
        # 清除旧选项
        for widget in self.option_widgets:
            self.layout.removeWidget(widget)
            widget.deleteLater()
        self.option_widgets = []
        self.button_group = QButtonGroup(self)  # 创建新的按钮组
        self.button_group.setExclusive(not (question['type'] == '多选题'))

        # 判断题目类型
        self.is_multiple = question['type'] == '多选题'

        # 创建选项按钮
        options = question['options']
        for key, text in options.items():
            if pd.isna(text) or text.strip() == "":
                continue

            if self.is_multiple:
                checkbox = QCheckBox(f"{key}. {text}")
                checkbox.setFont(self.original_font)  # 使用原始字体
                checkbox.setStyleSheet("""
                    QCheckBox {
                        padding: 20px;
                        border: 2px solid #E0E0E0;
                        border-radius: 10px;
                        background-color: #FFFFFF;
                        font-size: 25px;
                        font-family: "微软雅黑";
                    }
                    QCheckBox:hover {
                        border-color: #4A90E2;
                        background-color: #F5F9FF;
                    }
                    QCheckBox::indicator {
                        width: 25px;
                        height: 25px;
                    }
                """)
                self.button_group.addButton(checkbox)
                self.layout.addWidget(checkbox)
                self.option_widgets.append(checkbox)
            else:
                radio = QRadioButton(f"{key}. {text}")
                radio.setFont(self.original_font)  # 使用原始字体
                radio.setStyleSheet("""
                    QRadioButton {
                        padding: 20px;
                        border: 2px solid #E0E0E0;
                        border-radius: 10px;
                        background-color: #FFFFFF;
                        font-size: 25px;
                        font-family: "微软雅黑";
                    }
                    QRadioButton:hover {
                        border-color: #4A90E2;
                        background-color: #F5F9FF;
                    }
                    QRadioButton::indicator {
                        width: 25px;
                        height: 25px;
                    }
                """)
                # 连接单选按钮的点击信号到答案选择信号
                radio.toggled.connect(self._on_radio_toggled)
                self.button_group.addButton(radio)
                self.layout.addWidget(radio)
                self.option_widgets.append(radio)

        # 不再添加拉伸因子
        # 使用布局对齐方式控制位置

    def _on_radio_toggled(self, checked):
        """处理单选按钮选中状态变化"""
        # 只有在选中时才触发
        if checked:
            # 延迟发送信号，确保UI更新完成
            QTimer.singleShot(100, lambda: self.answer_selected.emit())

    def get_selected_answers(self):
        """获取选择的答案"""
        selected = []
        for btn in self.button_group.buttons():
            if btn.isChecked():
                # 从按钮文本中提取选项字母
                selected.append(btn.text()[0])
        return ''.join(selected)

    def set_correct_answers(self, correct_answers):
        """标记正确答案并放大字体"""
        for btn in self.button_group.buttons():
            option_key = btn.text()[0]
            if option_key in correct_answers:
                # 创建新字体 - 放大正确答案
                large_font = QFont("Arial", 30)  # 更大的字体
                large_font.setBold(True)  # 加粗
                btn.setFont(large_font)
                btn.setStyleSheet("color: green;")
            else:
                # 重置为原始字体
                btn.setFont(self.original_font)
                btn.setStyleSheet("")

    def reset_styles(self):
        """重置按钮样式和字体大小"""
        for btn in self.button_group.buttons():
            btn.setFont(self.original_font)  # 重置为原始字体
            btn.setStyleSheet("")


class MainWindow(QMainWindow):
    """主窗口类"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("刷题大师 - 专业考试练习系统")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)

        # 初始化管理器
        self.question_manager = QuestionManager()
        self.db_manager = DatabaseManager()

        # 创建UI
        self.init_ui()

        # 应用样式
        self.apply_light_theme()

        # 状态变量
        self.dark_mode = False
        self.showing_answer = False
        self.practice_tab = None  # 初始化 practice_tab
        self.feedback_label = QLabel(self)  # 初始化 feedback_label
        self.feedback_label.setAlignment(Qt.AlignCenter)
        self.feedback_label.setFont(QFont("微软雅黑", 100))  # 非常大的字体
        self.feedback_label.setVisible(False)
        self.feedback_label.setAttribute(Qt.WA_TransparentForMouseEvents)  # 鼠标事件穿透
        self.feedback_label.setStyleSheet("background: transparent; font-family: 微软雅黑;")
        self.initialized = False  # 初始化标志

        # 加载题库
        self.load_question_sets()

    def init_ui(self):
        """初始化用户界面"""
        # 创建主控件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # 创建顶部工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.mode_btn = QPushButton("🌙 夜间模式")
        self.mode_btn.setCheckable(True)
        self.mode_btn.clicked.connect(self.toggle_dark_mode)
        self.mode_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 15px;
                border-radius: 5px;
                font-weight: bold;
                font-family: "微软雅黑";
            }
        """)

        self.import_btn = QPushButton("📁 导入题库")
        self.import_btn.clicked.connect(self.import_questions)
        self.import_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 15px;
                border-radius: 5px;
                font-weight: bold;
                font-family: "微软雅黑";
            }
        """)

        self.export_btn = QPushButton("📊 导出错题")
        self.export_btn.clicked.connect(self.export_wrong_questions)
        self.export_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 15px;
                border-radius: 5px;
                font-weight: bold;
                font-family: "微软雅黑";
            }
        """)

        self.mark_btn = QPushButton("⭐ 标记题目")
        self.mark_btn.setCheckable(True)
        self.mark_btn.clicked.connect(self.toggle_mark_question)
        self.mark_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 15px;
                border-radius: 5px;
                font-weight: bold;
                font-family: "微软雅黑";
            }
            QPushButton:checked {
                background-color: #FFD700;
                color: black;
            }
        """)

        # 题库选择下拉框
        self.set_combo = QComboBox()
        self.set_combo.setMinimumWidth(200)
        self.set_combo.setStyleSheet("""
            QComboBox {
                padding: 8px 15px;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
                font-family: "微软雅黑";
            }
        """)
        self.set_combo.currentIndexChanged.connect(self.change_question_set)

        # 释放已掌握题目按钮
        self.release_btn = QPushButton("🔄 释放掌握")
        self.release_btn.clicked.connect(self.release_mastered_questions)
        self.release_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 15px;
                border-radius: 5px;
                font-weight: bold;
                font-family: "微软雅黑";
            }
        """)

        toolbar.addWidget(self.mode_btn)
        toolbar.addWidget(self.import_btn)
        toolbar.addWidget(self.export_btn)
        toolbar.addWidget(self.mark_btn)
        toolbar.addSpacing(20)
        toolbar.addWidget(QLabel("📚 选择题库:"))
        toolbar.addWidget(self.set_combo)
        toolbar.addWidget(self.release_btn)
        toolbar.addStretch()

        main_layout.addLayout(toolbar)

        # 创建标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 2px solid #CCCCCC;
                border-top: none;
                border-radius: 5px;
                padding: 10px;
                font-family: "微软雅黑";
            }
            QTabBar::tab {
                padding: 10px 20px;
                margin: 2px;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
                font-family: "微软雅黑";
            }
            QTabBar::tab:selected {
                background: #4A90E2;
                color: white;
            }
            QTabBar::tab:!selected {
                background: #F0F0F0;
            }
        """)
        main_layout.addWidget(self.tab_widget)

        # 创建答题页面
        self.create_practice_tab()

        # 创建错题本页面
        self.create_wrong_questions_tab()

        # 创建统计页面
        self.create_stats_tab()

        # 状态栏
        self.status_bar = self.statusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                padding: 5px;
                font-size: 12px;
                font-weight: bold;
                font-family: "微软雅黑";
            }
        """)
        self.status_bar.showMessage("✅ 就绪 - 欢迎使用刷题大师")

    def create_practice_tab(self):
        """创建答题页面"""
        tab = QWidget()
        self.practice_tab = tab  # 保存引用
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 题目内容区域 - 使用大字体
        self.question_label = QLabel()
        self.question_label.setWordWrap(True)
        self.question_label.setAlignment(Qt.AlignCenter)
        self.question_label.setFont(QFont("微软雅黑", 25, QFont.Bold))
        self.question_label.setStyleSheet("""
            QLabel {
                padding: 20px;
                border: 2px solid #4A90E2;
                border-radius: 10px;
                background-color: #F8F9FA;
                color: #333333;
                font-family: "微软雅黑";
            }
        """)
        # 设置题目区域高度策略，给更多空间
        question_policy = self.question_label.sizePolicy()
        question_policy.setVerticalStretch(2)  # 增加垂直拉伸因子
        self.question_label.setSizePolicy(question_policy)
        layout.addWidget(self.question_label)

        # 答案选项区域
        self.answer_widget = AnswerWidget()
        # 连接答案选择信号到自动提交函数
        self.answer_widget.answer_selected.connect(self.auto_submit_answer)
        # 设置选项区域高度策略，给更多空间
        answer_policy = self.answer_widget.sizePolicy()
        answer_policy.setVerticalStretch(3)  # 增加垂直拉伸因子
        self.answer_widget.setSizePolicy(answer_policy)
        layout.addWidget(self.answer_widget)

        # 解析区域
        self.explanation_browser = QTextBrowser()
        self.explanation_browser.setVisible(False)
        self.explanation_browser.setFont(QFont("微软雅黑", 14))
        self.explanation_browser.setStyleSheet("""
            QTextBrowser {
                padding: 15px;
                border: 2px solid #FF9800;
                border-radius: 10px;
                background-color: #FFF8E1;
                color: #333333;
                font-family: "微软雅黑";
            }
        """)
        # 设置解析区域高度策略
        explanation_policy = self.explanation_browser.sizePolicy()
        explanation_policy.setVerticalStretch(2)
        self.explanation_browser.setSizePolicy(explanation_policy)
        layout.addWidget(self.explanation_browser)

        # 导航按钮
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(15)

        self.prev_btn = QPushButton("⬅ 上一题")
        self.prev_btn.clicked.connect(self.prev_question)
        self.prev_btn.setStyleSheet("""
            QPushButton {
                padding: 12px 20px;
                font-size: 16px;
                font-weight: bold;
                border-radius: 8px;
                background-color: #90A4AE;
                color: white;
                font-family: "微软雅黑";
            }
            QPushButton:disabled {
                background-color: #CFD8DC;
            }
        """)

        self.submit_btn = QPushButton("✅ 提交答案")
        self.submit_btn.clicked.connect(self.submit_answer)
        self.submit_btn.setStyleSheet("""
            QPushButton {
                padding: 12px 20px;
                font-size: 16px;
                font-weight: bold;
                border-radius: 8px;
                background-color: #4CAF50;
                color: white;
                font-family: "微软雅黑";
            }
            QPushButton:disabled {
                background-color: #A5D6A7;
            }
        """)

        self.next_btn = QPushButton("下一题 ➡")
        self.next_btn.clicked.connect(self.next_question)
        self.next_btn.setStyleSheet("""
            QPushButton {
                padding: 12px 20px;
                font-size: 16px;
                font-weight: bold;
                border-radius: 8px;
                background-color: #2196F3;
                color: white;
                font-family: "微软雅黑";
            }
        """)

        self.show_explanation_btn = QPushButton("📘 显示解析")
        self.show_explanation_btn.clicked.connect(self.toggle_explanation)
        self.show_explanation_btn.setStyleSheet("""
            QPushButton {
                padding: 12px 20px;
                font-size: 16px;
                font-weight: bold;
                border-radius: 8px;
                background-color: #FF9800;
                color: white;
                font-family: "微软雅黑";
            }
        """)

        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.submit_btn)
        nav_layout.addWidget(self.next_btn)
        nav_layout.addWidget(self.show_explanation_btn)

        layout.addLayout(nav_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid grey;
                border-radius: 5px;
                text-align: center;
                height: 30px;
                font-family: "微软雅黑";
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                width: 20px;
            }
        """)
        self.progress_bar.setFont(QFont("微软雅黑", 15, QFont.Bold))  # 将字体大小从12改为15
        layout.addWidget(self.progress_bar)

        # 统计信息 - 减小高度
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(15)

        self.total_label = QLabel("📚 总题数: 0")
        self.answered_label = QLabel("✅ 已答: 0")
        self.correct_label = QLabel("✔ 正确: 0")
        self.mastered_label = QLabel("⭐ 已掌握: 0")
        self.unmastered_label = QLabel("📖 未掌握: 0")  # 新增未掌握题数标签

        stat_labels = [self.total_label, self.answered_label, self.correct_label, 
                      self.mastered_label, self.unmastered_label]
        
        for label in stat_labels:
            label.setStyleSheet("""
                QLabel {
                    padding: 5px;
                    border-radius: 8px;
                    font-size: 15px;  /* 将字体大小从12px改为15px */
                    font-weight: bold;
                    background-color: #E3F2FD;
                    color: #1976D2;
                    text-align: center;
                    font-family: "微软雅黑";
                }
            """)
            label.setAlignment(Qt.AlignCenter)
            # 减小标签高度
            label.setFixedHeight(40)

        stats_layout.addWidget(self.total_label)
        stats_layout.addWidget(self.answered_label)
        stats_layout.addWidget(self.correct_label)
        stats_layout.addWidget(self.mastered_label)
        stats_layout.addWidget(self.unmastered_label)
        stats_layout.addStretch()

        layout.addLayout(stats_layout)

        # 创建悬浮反馈标签（不参与布局）
        self.feedback_label = QLabel(tab)  # 使用答题练习标签页作为父控件
        self.feedback_label.setAlignment(Qt.AlignCenter)
        self.feedback_label.setFont(QFont("微软雅黑", 100, QFont.Bold))  # 非常大的字体
        self.feedback_label.setVisible(False)
        self.feedback_label.setAttribute(Qt.WA_TransparentForMouseEvents)  # 鼠标事件穿透
        self.feedback_label.setStyleSheet("background: transparent; font-family: 微软雅黑;")  # 背景透明
        self.feedback_label.setFixedSize(200, 200)  # 预设大小

        self.tab_widget.addTab(tab, "📖 答题练习")

    def create_wrong_questions_tab(self):
        """创建错题本页面"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 页面标题
        title_label = QLabel("❌ 错题本")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #F44336;
                padding: 10px;
                font-family: "微软雅黑";
            }
        """)
        layout.addWidget(title_label)

        # 错题列表
        self.wrong_list = QListWidget()
        self.wrong_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.wrong_list.itemDoubleClicked.connect(self.open_wrong_question)
        self.wrong_list.setFont(QFont("微软雅黑", 14))
        self.wrong_list.setStyleSheet("""
            QListWidget {
                border: 2px solid #FFCDD2;
                border-radius: 10px;
                padding: 10px;
                background-color: #FFFFFF;
                alternate-background-color: #FAFAFA;
                font-family: "微软雅黑";
                font-size: 14px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #EEEEEE;
            }
            QListWidget::item:selected {
                background-color: #FFCDD2;
                color: #B71C1C;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.wrong_list)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        self.refresh_btn = QPushButton("🔄 刷新列表")
        self.refresh_btn.clicked.connect(self.refresh_wrong_list)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                padding: 12px 20px;
                font-size: 16px;
                font-weight: bold;
                border-radius: 8px;
                background-color: #9C27B0;
                color: white;
                font-family: "微软雅黑";
            }
        """)

        self.practice_btn = QPushButton("💪 练习错题")
        self.practice_btn.clicked.connect(self.practice_wrong_questions)
        self.practice_btn.setStyleSheet("""
            QPushButton {
                padding: 12px 20px;
                font-size: 16px;
                font-weight: bold;
                border-radius: 8px;
                background-color: #FF5722;
                color: white;
                font-family: "微软雅黑";
            }
        """)

        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addWidget(self.practice_btn)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)

        self.tab_widget.addTab(tab, "❌ 错题本")

    def create_stats_tab(self):
        """创建统计页面"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # 页面标题
        title_label = QLabel("📈 学习统计")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #1976D2;
                padding: 15px;
                border-radius: 10px;
                background-color: #E3F2FD;
                font-family: "微软雅黑";
            }
        """)
        layout.addWidget(title_label)

        # 总体统计
        stats_frame = QFrame()
        stats_frame.setFrameShape(QFrame.StyledPanel)
        stats_frame.setStyleSheet("""
            QFrame {
                border: 2px solid #1976D2;
                border-radius: 15px;
                padding: 20px;
                background-color: #FFFFFF;
            }
        """)
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setSpacing(15)

        self.stats_title = QLabel("📊 详细统计信息")
        self.stats_title.setAlignment(Qt.AlignCenter)
        self.stats_title.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
                color: #1976D2;
                padding: 10px;
                font-family: "微软雅黑";
            }
        """)
        stats_layout.addWidget(self.stats_title)

        # 确保所有属性都已定义
        self.stats_total = QLabel("📚 总题数: 0")
        self.stats_answered = QLabel("✅ 已答题数: 0")
        self.stats_correct = QLabel("✔ 正确题数: 0")
        self.stats_wrong = QLabel("❌ 错误题数: 0")
        self.stats_mastered = QLabel("⭐ 已掌握题数: 0")
        self.stats_unmastered = QLabel("📖 未掌握题数: 0")  # 新增未掌握题数标签
        self.stats_accuracy = QLabel("🎯 正确率: 0%")

        # 设置统计信息字体和样式
        stat_labels = [self.stats_total, self.stats_answered, self.stats_correct,
                      self.stats_wrong, self.stats_mastered, self.stats_unmastered, 
                      self.stats_accuracy]
        
        for label in stat_labels:
            label.setStyleSheet("""
                QLabel {
                    padding: 12px;
                    border-radius: 8px;
                    font-size: 16px;
                    font-weight: bold;
                    background-color: #F5F5F5;
                    color: #333333;
                    font-family: "微软雅黑";
                }
            """)
            label.setFont(QFont("微软雅黑", 14))

        stats_layout.addWidget(self.stats_total)
        stats_layout.addWidget(self.stats_answered)
        stats_layout.addWidget(self.stats_correct)
        stats_layout.addWidget(self.stats_wrong)
        stats_layout.addWidget(self.stats_mastered)
        stats_layout.addWidget(self.stats_unmastered)
        stats_layout.addWidget(self.stats_accuracy)

        layout.addWidget(stats_frame)

        # 添加图表占位符
        chart_placeholder = QLabel("📊 学习进度图表 (功能开发中)")
        chart_placeholder.setAlignment(Qt.AlignCenter)
        chart_placeholder.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #9E9E9E;
                padding: 30px;
                border: 2px dashed #9E9E9E;
                border-radius: 10px;
                margin: 20px;
                font-family: "微软雅黑";
            }
        """)
        layout.addWidget(chart_placeholder)

        self.tab_widget.addTab(tab, "📈 学习统计")

    def load_question_sets(self):
        """加载题库"""
        try:
            print("开始加载题库...")
            # 扫描当前目录下名称包含"题库"的Excel文件
            question_files = glob.glob(os.path.join(os.getcwd(), "*题库*.xlsx"))
            question_files.extend(glob.glob(os.path.join(os.getcwd(), "*题库*.xls")))

            if not question_files:
                self.status_bar.showMessage("未找到题库文件，请导入题库")
                print("未找到题库文件")
                return

            print(f"找到 {len(question_files)} 个题库文件")

            # 加载所有题库文件
            for file_path in question_files:
                print(f"加载题库文件: {file_path}")
                success, message = self.question_manager.load_from_excel(file_path)
                if success:
                    self.status_bar.showMessage(message)
                    print(message)
                else:
                    QMessageBox.warning(self, "加载失败", message)
                    print(f"加载失败: {message}")

            # 更新题库选择下拉框
            self.set_combo.clear()
            self.set_combo.addItems(self.question_manager.question_sets.keys())
            print(f"更新题库选择下拉框: {len(self.question_manager.question_sets)} 个题库")

            # 尝试加载上次使用的题库
            print("尝试加载上次使用的题库...")
            # 先获取上次使用的题库名称
            cursor = self.db_manager.conn.cursor()
            cursor.execute("SELECT value FROM app_state WHERE key='last_set'")
            row = cursor.fetchone()
            last_set = row[0] if row else None
            
            if last_set and last_set in self.question_manager.question_sets:
                print(f"找到上次使用的题库: {last_set}")
                self.question_manager.set_current_set(last_set)
                self.set_combo.setCurrentText(last_set)
                
                # 加载该题库的进度和位置
                last_position, _, progress_rows = self.db_manager.load_progress(last_set)
                
                # 应用进度到当前题库
                if progress_rows:
                    print(f"应用进度到题库: {len(progress_rows)} 条记录")
                    # 创建题目ID到题目的映射
                    id_to_question = {q['id']: q for q in self.question_manager.questions}

                    # 应用进度
                    for row in progress_rows:
                        q_id, answered, correct, wrong, marked, mastered = row
                        if q_id in id_to_question:
                            q = id_to_question[q_id]
                            q['answered'] = answered
                            q['correct'] = correct
                            q['wrong'] = wrong
                            q['marked'] = bool(marked)
                            q['mastered'] = bool(mastered)
                            print(
                                f"应用进度: 题目ID={q_id}, 已答={answered}, 正确={correct}, 错误={wrong}, 标记={marked}, 掌握={mastered}")
                
                # 设置该题库的当前位置
                self.question_manager.current_question_index = last_position
                print(f"设置题库 {last_set} 的位置: {last_position}")
            else:
                # 默认选择第一个题库
                if self.question_manager.question_sets:
                    first_set = list(self.question_manager.question_sets.keys())[0]
                    print(f"未找到上次使用的题库，默认选择第一个题库: {first_set}")
                    self.question_manager.set_current_set(first_set)
                    self.set_combo.setCurrentText(first_set)
                    
                    # 加载默认题库的进度和位置
                    last_position, _, progress_rows = self.db_manager.load_progress(first_set)
                    
                    # 应用进度到当前题库
                    if progress_rows:
                        print(f"应用进度到题库: {len(progress_rows)} 条记录")
                        # 创建题目ID到题目的映射
                        id_to_question = {q['id']: q for q in self.question_manager.questions}

                        # 应用进度
                        for row in progress_rows:
                            q_id, answered, correct, wrong, marked, mastered = row
                            if q_id in id_to_question:
                                q = id_to_question[q_id]
                                q['answered'] = answered
                                q['correct'] = correct
                                q['wrong'] = wrong
                                q['marked'] = bool(marked)
                                q['mastered'] = bool(mastered)
                                print(
                                    f"应用进度: 题目ID={q_id}, 已答={answered}, 正确={correct}, 错误={wrong}, 标记={marked}, 掌握={mastered}")
                    
                    # 设置该题库的当前位置
                    self.question_manager.current_question_index = last_position
                    print(f"设置题库 {first_set} 的位置: {last_position}")

            # 显示该题库的当前位置题目
            print("显示当前位置题目...")
            self.show_question()
            self.update_progress()
            self.status_bar.showMessage("题库加载完成")
            print("题库加载完成")

            # 刷新错题列表
            print("刷新错题列表...")
            self.refresh_wrong_list()

            # 标记为已初始化
            self.initialized = True
            print("初始化完成")
        except Exception as e:
            QMessageBox.critical(self, "加载题库失败", str(e))
            print(f"加载题库失败: {str(e)}")
            traceback.print_exc()

    def show_first_unmastered_question(self):
        """显示第一个未掌握的题目"""
        # 找到第一个未掌握的题目
        for i in range(len(self.question_manager.questions)):
            if not self.question_manager.questions[i]['mastered']:
                self.question_manager.current_question_index = i
                break
        self.show_question()

    def change_question_set(self, index):
        """切换题库"""
        set_name = self.set_combo.currentText()
        if set_name and set_name in self.question_manager.question_sets:
            print(f"开始切换题库: {set_name}")

            # 保存当前题库进度
            print("保存当前题库进度...")
            self.save_current_progress()

            # 切换到新题库
            print(f"切换到新题库: {set_name}")
            self.question_manager.set_current_set(set_name)

            # 加载新题库的进度和位置
            print("加载新题库进度...")
            last_position, _, progress_rows = self.db_manager.load_progress(set_name)
            if progress_rows:
                print(f"应用进度到新题库: {len(progress_rows)} 条记录")
                # 创建题目ID到题目的映射
                id_to_question = {q['id']: q for q in self.question_manager.questions}

                # 应用进度
                for row in progress_rows:
                    q_id, answered, correct, wrong, marked, mastered = row
                    if q_id in id_to_question:
                        q = id_to_question[q_id]
                        q['answered'] = answered
                        q['correct'] = correct
                        q['wrong'] = wrong
                        q['marked'] = bool(marked)
                        q['mastered'] = bool(mastered)
                        print(
                            f"应用进度: 题目ID={q_id}, 已答={answered}, 正确={correct}, 错误={wrong}, 标记={marked}, 掌握={mastered}")

            # 设置新题库的当前位置
            self.question_manager.current_question_index = last_position
            print(f"设置题库 {set_name} 的位置: {last_position}")

            # 显示该题库的当前位置题目
            print("显示当前位置题目...")
            self.show_question()
            self.update_progress()
            self.status_bar.showMessage(f"已切换到题库: {set_name}")

            # 刷新错题列表
            print("刷新错题列表...")
            self.refresh_wrong_list()
            print(f"题库切换完成: {set_name}")

    def save_current_progress(self):
        """保存当前题库进度"""
        if self.initialized and self.question_manager.current_set and self.question_manager.questions:
            print(f"开始保存当前题库进度: {self.question_manager.current_set}")
            self.db_manager.save_progress(
                self.question_manager.questions,
                self.question_manager.current_question_index,
                self.question_manager.current_set
            )
            print(f"当前题库进度保存完成: {self.question_manager.current_set}")
        else:
            print("跳过保存进度: 未初始化或无题库")

    def show_question(self):
        """显示当前题目"""
        question = self.question_manager.get_current_question()
        if not question:
            return

        # 设置题目内容：第一行显示题型，第二行显示题号和内容（题号用不同颜色）
        q_text = f'<div style="text-align: center;">' \
                 f'<div style="font-size: 25px; color: #1976D2; font-weight: bold; font-family: 微软雅黑;">【{question["type"]}】</div>' \
                 f'<div><span style="color: #F44336; font-weight: bold; font-family: 微软雅黑;">{question["id"]}.</span> <span style="font-family: 微软雅黑;">{question["content"]}</span></div>' \
                 f'</div>'
        self.question_label.setText(q_text)
        self.question_label.setFont(QFont("微软雅黑", 25, QFont.Bold))

        # 设置答案选项
        self.answer_widget.set_question(question)

        # 重置解析区域
        explanation_html = f'<div style="font-family: 微软雅黑; font-size: 16px;">' \
                          f'<h3 style="color: #FF9800; margin-top: 0; font-family: 微软雅黑;">题目解析</h3>' \
                          f'<p style="font-family: 微软雅黑;">{question["explanation"]}</p>' \
                          f'</div>'
        self.explanation_browser.setHtml(explanation_html)
        self.explanation_browser.setVisible(False)
        self.show_explanation_btn.setText("📘 显示解析")

        # 更新标记按钮状态
        self.mark_btn.setChecked(question['marked'])

        # 更新导航按钮状态
        self.prev_btn.setEnabled(self.question_manager.prev_question_exists())
        self.next_btn.setEnabled(self.question_manager.next_question_exists())

        # 重置状态
        self.showing_answer = False
        self.submit_btn.setEnabled(True)
        self.answer_widget.reset_styles()

        # 隐藏反馈标签
        if self.feedback_label:  # 添加检查
            self.feedback_label.setVisible(False)

    def auto_submit_answer(self):
        """自动提交答案 - 用于单选题和判断题"""
        # 获取当前题目
        question = self.question_manager.get_current_question()
        if not question:
            return

        # 只对单选题和判断题自动提交
        if question['type'] in ['单选题', '判断题']:
            # 延迟一小段时间后提交，确保UI更新完成
            QTimer.singleShot(200, self.submit_answer)

    def submit_answer(self):
        """提交答案并检查"""
        print("提交答案按钮被点击")
        if self.showing_answer:
            print("当前正在显示答案，不处理")
            return

        question = self.question_manager.get_current_question()
        if not question:
            print("没有当前题目")
            return

        selected = self.answer_widget.get_selected_answers()
        if not selected:
            QMessageBox.warning(self, "未选择答案", "请先选择一个答案再提交！")
            return

        print(f"选择的答案: {selected}, 正确答案: {question['answer']}")

        # 检查答案
        is_correct = selected == question['answer']

        # 记录答题结果
        self.question_manager.record_answer(is_correct)

        # 显示正确答案
        self.answer_widget.set_correct_answers(question['answer'])

        # 显示结果消息
        if is_correct:
            self.status_bar.showMessage("回答正确！")
            # 显示对号
            if self.feedback_label:  # 确保反馈标签存在
                self.feedback_label.setText("✓")
                self.feedback_label.setStyleSheet("color: green; background: transparent;")
        else:
            self.status_bar.showMessage(f"回答错误！正确答案: {question['answer']}")
            # 显示错号
            if self.feedback_label:  # 确保反馈标签存在
                self.feedback_label.setText("✗")
                self.feedback_label.setStyleSheet("color: red; background: transparent;")

        # 调整反馈标签位置并显示
        if self.feedback_label:  # 确保反馈标签存在
            self.adjust_feedback_label_position()
            self.feedback_label.setVisible(True)
            self.feedback_label.raise_()  # 提升到最上层

        # 更新进度
        self.update_progress()

        # 刷新错题列表
        self.refresh_wrong_list()

        # 禁用提交按钮
        self.submit_btn.setEnabled(False)
        self.showing_answer = True

        # 0.5秒后隐藏反馈标签
        if self.feedback_label:  # 确保反馈标签存在
            QTimer.singleShot(500, self.hide_feedback)

        # 如果回答正确，0.5秒后自动下一题
        if is_correct:
            QTimer.singleShot(500, self.next_question)

    def next_question(self):
        """移动到下一题（跳过已掌握的题目）"""
        if self.question_manager.next_question():
            self.show_question()
        else:
            # 已经是最后一题，重置进度（除了已掌握的题目）
            self.question_manager.reset_progress(exclude_mastered=True)
            self.show_first_unmastered_question()
            self.update_progress()
            self.status_bar.showMessage("已重置进度（已掌握题目除外），开始新一轮答题")

            # 刷新错题列表
            self.refresh_wrong_list()

    def hide_feedback(self):
        """隐藏反馈标签"""
        if self.feedback_label:  # 确保反馈标签存在
            self.feedback_label.setVisible(False)

    def adjust_feedback_label_position(self):
        """调整反馈标签位置到中央"""
        if not self.feedback_label:  # 添加检查
            return

        # 获取答题练习标签页的中央位置
        if self.practice_tab:  # 确保练习标签页存在
            # 获取练习标签页在窗口中的位置
            center = self.practice_tab.rect().center()
            size = 200
            self.feedback_label.setFixedSize(size, size)
            # 相对于练习标签页移动标签到中央
            self.feedback_label.move(center.x() - size // 2, center.y() - size // 2)
        else:
            # 备用方案：使用主窗口中央位置
            center = self.rect().center()
            size = 200
            self.feedback_label.setFixedSize(size, size)
            self.feedback_label.move(center.x() - size // 2, center.y() - size // 2)

    def resizeEvent(self, event):
        """窗口大小改变时调整反馈标签位置"""
        super().resizeEvent(event)
        if self.feedback_label and self.feedback_label.isVisible():
            self.adjust_feedback_label_position()

    def prev_question(self):
        """移动到上一题（跳过已掌握的题目）"""
        if self.question_manager.prev_question():
            self.show_question()

    def toggle_explanation(self):
        """切换解析显示"""
        visible = not self.explanation_browser.isVisible()
        self.explanation_browser.setVisible(visible)
        self.show_explanation_btn.setText("隐藏解析" if visible else "显示解析")

    def toggle_mark_question(self):
        """标记/取消标记题目"""
        question = self.question_manager.get_current_question()
        if question:
            question['marked'] = self.mark_btn.isChecked()
            if question['marked']:
                self.status_bar.showMessage("题目已标记")
            else:
                self.status_bar.showMessage("题目取消标记")

    def update_progress(self):
        """更新进度信息"""
        total, answered, correct, mastered, unmastered = self.question_manager.get_progress()

        # 更新答题页面统计
        self.total_label.setText(f"总题数: {total}")
        self.answered_label.setText(f"已答: {answered}")
        self.correct_label.setText(f"正确: {correct}")
        self.mastered_label.setText(f"已掌握: {mastered}")
        self.unmastered_label.setText(f"未掌握: {unmastered}")

        # 更新统计页面
        self.stats_total.setText(f"总题数: {total}")
        self.stats_answered.setText(f"已答题数: {answered}")
        self.stats_correct.setText(f"正确题数: {correct}")
        self.stats_wrong.setText(f"错误题数: {answered - correct}")
        self.stats_mastered.setText(f"已掌握题数: {mastered}")
        self.stats_unmastered.setText(f"未掌握题数: {unmastered}")

        # 计算正确率
        accuracy = (correct / answered * 100) if answered > 0 else 0
        self.stats_accuracy.setText(f"正确率: {accuracy:.1f}%")

        # 更新进度条
        progress = (answered / total * 100) if total > 0 else 0
        self.progress_bar.setValue(int(progress))

    def refresh_wrong_list(self):
        """刷新错题列表"""
        self.wrong_list.clear()
        wrong_questions = self.question_manager.get_wrong_questions()

        for q in wrong_questions:
            item = QListWidgetItem(f"{q['id']}. {q['content'][:50]}... (错误次数: {q['wrong']})")
            item.setData(Qt.UserRole, q['id'])
            self.wrong_list.addItem(item)

    def open_wrong_question(self, item):
        """打开选中的错题"""
        q_id = item.data(Qt.UserRole)
        # 找到题目索引
        for idx, q in enumerate(self.question_manager.questions):
            if q['id'] == q_id:
                self.question_manager.current_question_index = idx
                self.tab_widget.setCurrentIndex(0)  # 切换到答题页
                self.show_question()
                break

    def practice_wrong_questions(self):
        """练习错题"""
        wrong_questions = self.question_manager.get_wrong_questions()
        if not wrong_questions:
            QMessageBox.information(self, "没有错题", "当前没有错题，太棒了！")
            return

        # 切换到答题页
        self.tab_widget.setCurrentIndex(0)

        # 设置错题为当前题库
        self.question_manager.questions = wrong_questions
        self.question_manager.current_question_index = 0
        self.show_question()
        self.update_progress()

        self.status_bar.showMessage(f"开始练习错题，共 {len(wrong_questions)} 道")

    def toggle_dark_mode(self):
        """切换夜间模式"""
        self.dark_mode = not self.dark_mode
        self.mode_btn.setText("☀️ 日间模式" if self.dark_mode else "🌙 夜间模式")

        if self.dark_mode:
            self.apply_dark_theme()
        else:
            self.apply_light_theme()

    def apply_light_theme(self):
        """应用浅色主题"""
        palette = self.palette()
        # 使用 QPalette.ColorRole 枚举
        palette.setColor(QPalette.ColorRole.Window, QColor(245, 245, 245))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
        palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.black)
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
        palette.setColor(QPalette.ColorRole.Button, QColor(248, 248, 248))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Highlight, QColor(74, 144, 226))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
        self.setPalette(palette)

        # 额外样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #F5F5F5;
                font-family: "微软雅黑";
            }
            QTabWidget::pane { 
                border: 2px solid #CCCCCC; 
                border-top: none;
                border-radius: 8px;
                background-color: white;
                padding: 10px;
                font-family: "微软雅黑";
            }
            QTabBar::tab { 
                background: #E0E0E0; 
                padding: 12px 25px; 
                border: 2px solid #CCCCCC; 
                border-bottom: none; 
                border-top-left-radius: 8px; 
                border-top-right-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                font-family: "微软雅黑";
            }
            QTabBar::tab:selected { 
                background: #4A90E2; 
                color: white;
                border-color: #4A90E2;
            }
            QFrame { 
                background: white; 
                border-radius: 8px;
            }
            QLabel, QRadioButton, QCheckBox, QTextBrowser { 
                color: #333333; 
                font-family: "微软雅黑";
            }
            QComboBox {
                padding: 8px 15px;
                border-radius: 5px;
                border: 2px solid #CCCCCC;
                background-color: white;
                font-family: "微软雅黑";
            }
            QComboBox:hover {
                border-color: #4A90E2;
            }
            QComboBox::drop-down {
                border-left: 2px solid #CCCCCC;
            }
            QPushButton {
                font-family: "微软雅黑";
            }
            QProgressBar {
                font-family: "微软雅黑";
            }
        """)

    def apply_dark_theme(self):
        """应用深色主题"""
        palette = self.palette()
        # 使用 QPalette.ColorRole 枚举
        palette.setColor(QPalette.ColorRole.Window, QColor(40, 40, 40))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(45, 45, 45))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(25, 25, 25))
        palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Button, QColor(50, 50, 50))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Highlight, QColor(74, 144, 226))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
        self.setPalette(palette)

        # 额外样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #282828;
                font-family: "微软雅黑";
            }
            QTabWidget::pane { 
                border: 2px solid #555555; 
                border-top: none;
                border-radius: 8px;
                background-color: #333333;
                padding: 10px;
                font-family: "微软雅黑";
            }
            QTabBar::tab { 
                background: #444444; 
                color: #CCCCCC;
                padding: 12px 25px; 
                border: 2px solid #555555; 
                border-bottom: none; 
                border-top-left-radius: 8px; 
                border-top-right-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                font-family: "微软雅黑";
            }
            QTabBar::tab:selected { 
                background: #4A90E2; 
                color: white;
                border-color: #4A90E2;
            }
            QFrame { 
                background: #333333; 
                border-radius: 8px;
            }
            QLabel, QRadioButton, QCheckBox, QTextBrowser { 
                color: #EEEEEE; 
                font-family: "微软雅黑";
            }
            QComboBox {
                padding: 8px 15px;
                border-radius: 5px;
                border: 2px solid #555555;
                background-color: #333333;
                color: #EEEEEE;
                font-family: "微软雅黑";
            }
            QComboBox:hover {
                border-color: #4A90E2;
            }
            QComboBox::drop-down {
                border-left: 2px solid #555555;
            }
            QPushButton {
                font-family: "微软雅黑";
            }
            QProgressBar {
                font-family: "微软雅黑";
            }
        """)

    def import_questions(self):
        """导入题库"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择题库文件", "", "Excel文件 (*.xlsx *.xls)"
        )

        if file_path:
            success, message = self.question_manager.load_from_excel(file_path)
            if success:
                # 更新题库选择下拉框
                self.set_combo.clear()
                self.set_combo.addItems(self.question_manager.question_sets.keys())
                self.set_combo.setCurrentText(self.question_manager.current_set)

                # 显示第一题（跳过已掌握的题目）
                self.show_first_unmastered_question()
                self.update_progress()
                self.status_bar.showMessage(message)

                # 刷新错题列表
                self.refresh_wrong_list()
            else:
                QMessageBox.critical(self, "导入失败", message)

    def export_wrong_questions(self):
        """导出错题为PDF"""
        wrong_questions = self.question_manager.get_wrong_questions()
        if not wrong_questions:
            QMessageBox.information(self, "没有错题", "当前没有错题可导出")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出错题", "错题集.pdf", "PDF文件 (*.pdf)"
        )

        if file_path:
            try:
                printer = QPrinter(QPrinter.HighResolution)
                printer.setOutputFormat(QPrinter.PdfFormat)
                printer.setOutputFileName(file_path)

                doc = QTextDocument()
                html = f"<h1>错题集 - {self.question_manager.current_set}</h1>"

                for q in wrong_questions:
                    html += f"""
                    <div style="margin-bottom: 20px; border: 1px solid #ccc; padding: 10px; page-break-inside: avoid;">
                        <p> {q['id']}: {q['content']}</p>
                        <!-- <p>题型: {q['type']}</p>
                        <p>选项:</p> -->
                        <ul>
                    """

                    for key, text in q['options'].items():
                        if pd.isna(text) or text.strip() == "":
                            continue
                        html += f"<li>{key}. {text}</li>"

                    html += f"""
                        </ul>
                        <p><b>正确答案: {q['answer']}</b></p>
                        <!-- <p>解析: {q['explanation']}</p> 
                        <p>错误次数: {q['wrong']}</p> -->
                    </div>
                    """

                doc.setHtml(html)
                doc.print_(printer)

                self.status_bar.showMessage(f"成功导出 {len(wrong_questions)} 道错题到 {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "导出失败", f"导出PDF时出错: {str(e)}")

    def release_mastered_questions(self):
        """释放已掌握的题目"""
        # 统计不同错误次数的已掌握题目数量
        mastered_questions = [q for q in self.question_manager.questions if q['mastered']]
        
        if not mastered_questions:
            QMessageBox.information(self, "无已掌握题目", "当前没有已掌握的题目")
            return
            
        # 按错误次数统计
        error_count_stats = {}
        for q in mastered_questions:
            wrong_count = q['wrong']
            error_count_stats[wrong_count] = error_count_stats.get(wrong_count, 0) + 1
        
        # 构建统计信息文本
        stats_text = "已掌握题目按错误次数分布:\n"
        for error_count in sorted(error_count_stats.keys()):
            stats_text += f"错误 {error_count} 次: {error_count_stats[error_count]} 题\n"
        
        stats_text += "\n请输入错误次数的阈值:"

        # 弹出对话框让用户选择错误次数阈值，并显示统计信息
        threshold, ok = QInputDialog.getInt(
            self, "释放已掌握题目",
            stats_text,
            1, 0, 10, 1
        )

        if not ok:
            return

        # 释放已掌握题目
        count = self.question_manager.release_mastered_questions_by_wrong_count(threshold)

        # 更新进度
        self.update_progress()

        self.status_bar.showMessage(f"已释放 {count} 道错误次数达到 {threshold} 次的题目")

        # 刷新错题列表
        self.refresh_wrong_list()

        # 重新开始新一轮刷题
        self.question_manager.reset_progress(exclude_mastered=True)
        self.show_first_unmastered_question()
        self.update_progress()
        self.status_bar.showMessage("已重置进度（已掌握题目除外），开始新一轮答题")

    def keyPressEvent(self, event):
        """键盘事件处理"""
        # 只在答题页面处理A键
        if self.tab_widget.currentIndex() == 0:
            if event.key() == Qt.Key_A:  # 将空格键改为A键
                if not self.showing_answer:
                    # 未提交，执行提交
                    self.submit_answer()
                else:
                    # 已提交，执行下一题
                    self.next_question()
                event.accept()  # 确保事件被处理
                return  # 直接返回，不再传递事件

        # 其他情况调用父类处理
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        """鼠标事件处理"""
        # 只在答题页面处理右键点击
        if self.tab_widget.currentIndex() == 0:
            if event.button() == Qt.MouseButton.RightButton:
                if not self.showing_answer:
                    # 未提交，执行提交
                    self.submit_answer()
                else:
                    # 已提交，执行下一题
                    self.next_question()
                event.accept()  # 确保事件被处理
                return  # 直接返回，不再传递事件

        # 其他情况调用父类处理
        super().mousePressEvent(event)

    def closeEvent(self, event):
        """关闭窗口时保存进度"""
        if self.initialized:
            print("关闭窗口，保存进度...")
            self.save_current_progress()
            print("进度保存完成")
        else:
            print("关闭窗口，跳过保存进度（未初始化）")
        event.accept()


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")

        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"程序启动失败: {str(e)}")
        traceback.print_exc()