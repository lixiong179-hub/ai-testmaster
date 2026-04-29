"""文件解析服务 - 支持多种文件格式的统一解析接口。

本模块提供文件解析的工厂模式实现，支持txt/md/doc/docx/pdf等
常见文件格式的解析。通过FileParserFactory统一创建解析器，
屏蔽不同格式的解析细节。

核心类:
    - FileParser: 文件解析器抽象基类
    - TxtParser: 文本文件解析器（支持UTF-8/GBK编码回退）
    - MdParser: Markdown文件解析器
    - DocParser: Word文档解析器（.doc格式）
    - DocxParser: Word文档解析器（.docx格式）
    - PdfParser: PDF文件解析器
    - FileParserFactory: 文件解析器工厂

设计模式:
    采用工厂模式，FileParserFactory根据文件扩展名创建对应的解析器。
    所有解析器继承FileParser抽象基类，实现统一的parse接口。

依赖关系:
    - python-docx: Word文档解析（pip install python-docx）
    - PyPDF2: PDF文档解析（pip install PyPDF2）

编码兼容:
    TxtParser和MdParser支持UTF-8/GBK编码自动回退，
    确保中文文件在不同编码环境下均可正常解析。
"""
import os
import re
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class FileParser(ABC):
    """文件解析器抽象基类 - 定义统一的parse接口。

    所有具体解析器必须实现parse方法，接受文件路径，
    返回解析后的文本内容。
    """

    @abstractmethod
    def parse(self, file_path: str) -> str:
        """解析文件内容。

        Args:
            file_path: 文件绝对路径。

        Returns:
            解析后的文本内容字符串。
        """
        pass


class TxtParser(FileParser):
    """文本文件解析器 - 支持UTF-8和GBK编码自动回退。

    优先使用UTF-8编码读取，失败时回退到GBK编码，
    确保中文文本文件在不同编码环境下均可正常解析。
    """

    def parse(self, file_path: str) -> str:
        """解析文本文件，UTF-8编码失败时回退到GBK。

        Args:
            file_path: 文本文件路径。

        Returns:
            文件文本内容。
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # UTF-8解码失败，回退到GBK编码
            with open(file_path, 'r', encoding='gbk') as f:
                return f.read()


class MdParser(FileParser):
    """Markdown文件解析器 - 与TxtParser相同的编码回退策略。"""

    def parse(self, file_path: str) -> str:
        """解析Markdown文件，UTF-8编码失败时回退到GBK。

        Args:
            file_path: Markdown文件路径。

        Returns:
            文件文本内容。
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='gbk') as f:
                return f.read()


class DocParser(FileParser):
    """Word文档解析器（.doc格式） - 使用python-docx库解析。

    注意：python-docx主要支持.docx格式，对旧版.doc格式
    支持有限，复杂格式可能丢失。
    """

    def parse(self, file_path: str) -> str:
        """解析Word文档，提取所有段落文本。

        Args:
            file_path: Word文档路径。

        Returns:
            段落文本拼接结果，解析失败时返回错误信息。
        """
        try:
            import docx
            doc = docx.Document(file_path)
            text = []
            for paragraph in doc.paragraphs:
                text.append(paragraph.text)
            return '\n'.join(text)
        except ImportError:
            return "需要安装 python-docx 库来解析Word文档"
        except Exception as e:
            return f"解析Word文档失败: {str(e)}"


class DocxParser(FileParser):
    """Word文档解析器（.docx格式） - 使用python-docx库解析。"""

    def parse(self, file_path: str) -> str:
        """解析Word文档，提取所有段落文本。

        Args:
            file_path: Word文档路径。

        Returns:
            段落文本拼接结果，解析失败时返回错误信息。
        """
        try:
            import docx
            doc = docx.Document(file_path)
            text = []
            for paragraph in doc.paragraphs:
                text.append(paragraph.text)
            return '\n'.join(text)
        except ImportError:
            return "需要安装 python-docx 库来解析Word文档"
        except Exception as e:
            return f"解析Word文档失败: {str(e)}"


class PdfParser(FileParser):
    """PDF文件解析器 - 使用PyPDF2库解析，提取每页文本。"""

    def parse(self, file_path: str) -> str:
        """解析PDF文档，逐页提取文本内容。

        Args:
            file_path: PDF文件路径。

        Returns:
            各页文本拼接结果，解析失败时返回错误信息。
        """
        try:
            import PyPDF2
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                text = []
                for page_num in range(len(reader.pages)):
                    page = reader.pages[page_num]
                    text.append(page.extract_text())
                return '\n'.join(text)
        except ImportError:
            return "需要安装 PyPDF2 库来解析PDF文档"
        except Exception as e:
            return f"解析PDF文档失败: {str(e)}"


class FileParserFactory:
    """文件解析器工厂 - 根据文件扩展名创建对应的解析器实例。

    支持的文件格式:
        - .txt: 纯文本文件
        - .md: Markdown文件
        - .doc: Word文档（旧格式）
        - .docx: Word文档（新格式）
        - .pdf: PDF文档

    使用方式:
        content = FileParserFactory.parse_file("/path/to/file.pdf")
    """

    @staticmethod
    def get_parser(file_extension: str) -> Optional[FileParser]:
        """根据文件扩展名获取对应的解析器实例。

        Args:
            file_extension: 文件扩展名（含点号），如".pdf"。

        Returns:
            FileParser实例，不支持的格式返回None。
        """
        parsers = {
            '.txt': TxtParser(),
            '.md': MdParser(),
            '.doc': DocParser(),
            '.docx': DocxParser(),
            '.pdf': PdfParser()
        }
        return parsers.get(file_extension.lower())

    @staticmethod
    def parse_file(file_path: str) -> str:
        """解析文件，自动根据扩展名选择解析器。

        Args:
            file_path: 文件路径。

        Returns:
            解析后的文本内容，不支持的格式返回错误提示。
        """
        file_extension = os.path.splitext(file_path)[1]
        parser = FileParserFactory.get_parser(file_extension)
        if parser:
            return parser.parse(file_path)
        else:
            return f"不支持的文件类型: {file_extension}"
