import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urljoin, urlparse
import json
import os
from datetime import datetime
import logging
from typing import Dict, List, Optional
import random

def safe_print(message_with_emoji, message_plain=""):
    """안전한 출력 (Windows 유니코드 호환)"""
    try:
        print(message_with_emoji)
    except UnicodeEncodeError:
        print(message_plain if message_plain else message_with_emoji.encode('ascii', 'ignore').decode('ascii'))

class RexResearchCrawler:
    def __init__(self, base_url: str = "https://www.rexresearch.com/invnindx.html"):
        self.base_url = base_url
        self.base_domain = "https://www.rexresearch.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # 로깅 설정 (Windows 유니코드 호환)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('rex_research_crawler.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        # Windows 콘솔 인코딩 설정
        import sys
        if sys.platform == "win32":
            try:
                # UTF-8 콘솔 출력 설정 시도
                import codecs
                sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
                sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
            except:
                # 실패 시 로그에서 이모지 제거 모드로 변경
                self.use_emoji = False
        else:
            self.use_emoji = True
        self.logger = logging.getLogger(__name__)
        
        # 이모지 사용 여부 (Windows 호환성)
        self.use_emoji = True
        
        # 데이터 저장용
        self.inventions_data = []
        self.visited_urls = set()
        self.request_delay = (1, 3)  # 1-3초 랜덤 지연
        
        # 출력 디렉토리
        self.output_dir = "rex_inventions"
    
    def _estimate_time(self, num_pages: int) -> int:
        """예상 소요시간 계산 (분 단위)"""
        # 평균 지연시간 + 페이지 로드 시간 고려
        avg_delay = sum(self.request_delay) / 2
        avg_processing_time = 2  # 페이지 처리 시간
        total_seconds = num_pages * (avg_delay + avg_processing_time)
        return max(1, int(total_seconds / 60))
    
    def safe_log(self, level, message_with_emoji, message_plain):
        """안전한 로그 출력 (Windows 유니코드 호환)"""
        try:
            if hasattr(self, 'use_emoji') and self.use_emoji:
                getattr(self.logger, level)(message_with_emoji)
            else:
                getattr(self.logger, level)(message_plain)
        except UnicodeEncodeError:
            # 이모지 사용 실패 시 일반 텍스트로 대체
            self.use_emoji = False
            getattr(self.logger, level)(message_plain)
        
    def create_output_directory(self):
        """출력 디렉토리 생성"""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            self.safe_log('info', f"📁 출력 디렉토리 생성: {self.output_dir}", 
                         f"[CREATE] 출력 디렉토리 생성: {self.output_dir}")
        
    def get_page(self, url: str, retries: int = 3) -> Optional[BeautifulSoup]:
        """페이지를 가져오고 BeautifulSoup 객체로 반환"""
        for attempt in range(retries):
            try:
                time.sleep(random.uniform(*self.request_delay))
                
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                
                # 인코딩 처리
                if response.encoding is None:
                    response.encoding = 'utf-8'
                elif response.encoding.lower() in ['iso-8859-1', 'windows-1252']:
                    response.encoding = 'utf-8'
                
                soup = BeautifulSoup(response.text, 'html.parser')
                self.safe_log('info', f"✅ 페이지 로드 성공: {url}", f"[SUCCESS] 페이지 로드 성공: {url}")
                return soup
                
            except requests.RequestException as e:
                self.safe_log('warning', f"⚠️ 페이지 로드 실패 (시도 {attempt + 1}/{retries}): {url} - {e}", 
                            f"[WARNING] 페이지 로드 실패 (시도 {attempt + 1}/{retries}): {url} - {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    
        self.safe_log('error', f"❌ 모든 시도 실패: {url}", f"[ERROR] 모든 시도 실패: {url}")
        return None
    
    def extract_invention_links(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """메인 페이지에서 발명품/발명자 링크들을 추출"""
        invention_links = []
        
        # 모든 링크 찾기
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link.get('href', '').strip()
            text = link.get_text(strip=True)
            
            if not href or not text:
                continue
                
            # 발명품/발명자 링크인지 판단
            if self.is_invention_link(href, text):
                full_url = urljoin(self.base_domain, href)
                
                invention_links.append({
                    'name': text,
                    'url': full_url,
                    'href': href,
                    'category': self.get_link_category(text)
                })
        
        # 중복 제거
        seen_urls = set()
        unique_links = []
        for link in invention_links:
            if link['url'] not in seen_urls:
                seen_urls.add(link['url'])
                unique_links.append(link)
        
        self.safe_log('info', f"📋 총 {len(unique_links)}개의 발명품 링크 발견", 
                     f"[INFO] 총 {len(unique_links)}개의 발명품 링크 발견")
        return unique_links
    
    def is_invention_link(self, href: str, text: str) -> bool:
        """링크가 발명품/발명자 관련인지 판단"""
        href_lower = href.lower()
        text_lower = text.lower()
        
        # 제외할 패턴들
        exclude_patterns = [
            'javascript:', 'mailto:', '#', 'http://', 'https://',
            'index.html', 'home.html', 'about.html', 'contact.html',
            'search.html', 'links.html', 'disclaimer.html'
        ]
        
        exclude_texts = [
            'home', 'back', 'top', 'index', 'search', 'contact',
            'about', 'links', 'disclaimer', 'rexresearch',
            'inventor index', 'subject index'
        ]
        
        # 제외 패턴 체크
        for pattern in exclude_patterns:
            if pattern in href_lower:
                return False
        
        for pattern in exclude_texts:
            if pattern in text_lower:
                return False
        
        # 유효한 링크 조건
        return (
            href.endswith('.html') and 
            len(text) > 2 and 
            not text.isdigit() and
            not text.startswith('[') and
            not text.startswith('(') and
            len(text) < 200  # 너무 긴 텍스트 제외
        )
    
    def get_link_category(self, text: str) -> str:
        """링크의 카테고리 추정"""
        text_lower = text.lower()
        
        # 에너지 관련
        energy_keywords = ['energy', 'power', 'electric', 'magnetic', 'battery', 'fuel', 'solar', 'generator']
        if any(keyword in text_lower for keyword in energy_keywords):
            return 'energy'
        
        # 의료 관련
        medical_keywords = ['medical', 'health', 'therapy', 'healing', 'cure', 'treatment']
        if any(keyword in text_lower for keyword in medical_keywords):
            return 'medical'
        
        # 교통 관련
        transport_keywords = ['car', 'vehicle', 'engine', 'motor', 'aviation', 'aircraft']
        if any(keyword in text_lower for keyword in transport_keywords):
            return 'transport'
        
        return 'general'
    
    def clean_text(self, text: str) -> str:
        """텍스트 정리"""
        if not text:
            return ""
        
        # HTML 엔티티 처리
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&apos;', "'")
        
        # 여러 공백과 줄바꿈 정리
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        return text.strip()
    
    def extract_invention_content(self, soup: BeautifulSoup, url: str, name: str) -> Dict:
        """개별 발명품 페이지에서 상세 내용 추출"""
        invention_data = {
            'name': name,
            'url': url,
            'extracted_at': datetime.now().isoformat(),
            'title': '',
            'description': '',
            'principle': '',
            'technical_details': [],
            'patents': [],
            'images': [],
            'diagrams': [],
            'references': [],
            'full_content': '',
            'structured_sections': {}
        }
        
        try:
            # 페이지 제목
            title_tag = soup.find('title')
            if title_tag:
                invention_data['title'] = self.clean_text(title_tag.get_text())
            
            # 메타 설명
            meta_desc = soup.find('meta', {'name': 'description'})
            if meta_desc:
                invention_data['meta_description'] = meta_desc.get('content', '')
            
            # 본문 텍스트 추출
            full_text = soup.get_text(separator='\n', strip=True)
            invention_data['full_content'] = self.clean_text(full_text)
            
            # 구조화된 섹션 추출
            self.extract_structured_sections(soup, invention_data)
            
            # 이미지 및 다이어그램 추출
            self.extract_images_and_diagrams(soup, url, invention_data)
            
            # 특허 정보 추출
            self.extract_patent_info(full_text, invention_data)
            
            # 참조 링크 추출
            self.extract_references(soup, invention_data)
            
            # 기술적 원리 추출
            self.extract_technical_principle(soup, invention_data)
            
        except Exception as e:
            self.safe_log('error', f"❌ 컨텐츠 추출 중 오류: {url} - {e}", 
                         f"[ERROR] 컨텐츠 추출 중 오류: {url} - {e}")
        
        return invention_data
    
    def extract_structured_sections(self, soup: BeautifulSoup, invention_data: Dict):
        """구조화된 섹션 추출"""
        sections = {}
        
        # 헤딩으로 섹션 구분
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        
        for heading in headings:
            heading_text = self.clean_text(heading.get_text())
            if heading_text:
                # 헤딩 다음의 컨텐츠 추출
                content = []
                current = heading.next_sibling
                
                while current and current.name not in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    if hasattr(current, 'get_text'):
                        text = self.clean_text(current.get_text())
                        if text and len(text) > 10:
                            content.append(text)
                    current = current.next_sibling
                    if not current:
                        break
                
                if content:
                    sections[heading_text] = content
        
        invention_data['structured_sections'] = sections
        
        # 주요 문단들 추출
        paragraphs = soup.find_all('p')
        tech_details = []
        for p in paragraphs:
            text = self.clean_text(p.get_text())
            if text and len(text) > 50:  # 의미있는 길이의 문단만
                tech_details.append(text)
        
        invention_data['technical_details'] = tech_details
    
    def extract_images_and_diagrams(self, soup: BeautifulSoup, base_url: str, invention_data: Dict):
        """이미지 및 다이어그램 정보 추출"""
        images = soup.find_all('img')
        
        for img in images:
            src = img.get('src', '')
            alt = img.get('alt', '')
            title = img.get('title', '')
            
            if src:
                full_img_url = urljoin(base_url, src)
                filename = os.path.basename(src)
                
                img_info = {
                    'url': full_img_url,
                    'filename': filename,
                    'alt_text': self.clean_text(alt),
                    'title': self.clean_text(title),
                    'type': self.classify_image_type(filename, alt)
                }
                
                if img_info['type'] == 'diagram':
                    invention_data['diagrams'].append(img_info)
                else:
                    invention_data['images'].append(img_info)
    
    def classify_image_type(self, filename: str, alt_text: str) -> str:
        """이미지 타입 분류"""
        filename_lower = filename.lower()
        alt_lower = alt_text.lower()
        
        diagram_keywords = ['diagram', 'schematic', 'circuit', 'blueprint', 'plan', 'design']
        photo_keywords = ['photo', 'picture', 'image']
        
        if any(keyword in filename_lower or keyword in alt_lower for keyword in diagram_keywords):
            return 'diagram'
        elif any(keyword in filename_lower or keyword in alt_lower for keyword in photo_keywords):
            return 'photo'
        else:
            return 'image'
    
    def extract_patent_info(self, text: str, invention_data: Dict):
        """특허 정보 추출"""
        patent_patterns = [
            r'(?:US\s*)?Patent\s+(?:No\.?\s*)?(\d{1,2}[,.\s]?\d{3}[,.\s]?\d{3})',
            r'U\.S\.\s*Patent\s+(\d{1,2}[,.\s]?\d{3}[,.\s]?\d{3})',
            r'Patent\s+#\s*(\d{1,2}[,.\s]?\d{3}[,.\s]?\d{3})',
            r'Pat\.\s*No\.\s*(\d{1,2}[,.\s]?\d{3}[,.\s]?\d{3})'
        ]
        
        patents = set()
        for pattern in patent_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                clean_patent = re.sub(r'[,.\s]', '', match)
                if len(clean_patent) >= 6:  # 유효한 특허 번호 길이
                    patents.add(clean_patent)
        
        invention_data['patents'] = list(patents)
    
    def extract_references(self, soup: BeautifulSoup, invention_data: Dict):
        """참조 링크 추출"""
        links = soup.find_all('a', href=True)
        references = []
        
        for link in links:
            href = link.get('href', '')
            text = self.clean_text(link.get_text())
            
            if href and text and href.startswith('http'):
                references.append({
                    'url': href,
                    'text': text
                })
        
        invention_data['references'] = references
    
    def extract_technical_principle(self, soup: BeautifulSoup, invention_data: Dict):
        """기술적 원리 및 설명 추출"""
        # 전체 텍스트에서 원리 관련 부분 찾기
        full_text = invention_data['full_content']
        
        # 원리 관련 키워드로 섹션 찾기
        principle_keywords = [
            'principle', 'theory', 'mechanism', 'operation', 'working',
            'function', 'process', 'method', 'technique', 'approach'
        ]
        
        # 문단별로 분석하여 원리 설명 추출
        paragraphs = invention_data['technical_details']
        principle_paragraphs = []
        
        for paragraph in paragraphs:
            paragraph_lower = paragraph.lower()
            if any(keyword in paragraph_lower for keyword in principle_keywords):
                principle_paragraphs.append(paragraph)
        
        if principle_paragraphs:
            invention_data['principle'] = '\n\n'.join(principle_paragraphs[:3])  # 처음 3개 문단
        else:
            # 원리 설명이 없으면 첫 번째 의미있는 문단을 설명으로
            if paragraphs:
                invention_data['description'] = paragraphs[0]
    
    def save_invention_file(self, invention_data: Dict) -> str:
        """개별 발명품 파일 저장 (LLM 학습용 형식)"""
        # 안전한 파일명 생성
        name = invention_data.get('name', 'unknown')
        safe_name = re.sub(r'[^\w\s-]', '', name).strip()
        safe_name = re.sub(r'[-\s]+', '_', safe_name)
        safe_name = safe_name[:100]  # 파일명 길이 제한
        
        filename = f"{safe_name}.txt"
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                # LLM 학습용 구조화된 형식
                f.write("=" * 80 + "\n")
                f.write(f"INVENTION: {invention_data.get('name', 'Unknown')}\n")
                f.write("=" * 80 + "\n\n")
                
                # 기본 정보
                f.write("BASIC INFORMATION:\n")
                f.write("-" * 40 + "\n")
                f.write(f"Title: {invention_data.get('title', 'N/A')}\n")
                f.write(f"URL: {invention_data.get('url', 'N/A')}\n")
                f.write(f"Extraction Date: {invention_data.get('extracted_at', 'N/A')}\n\n")
                
                # 특허 정보
                patents = invention_data.get('patents', [])
                if patents:
                    f.write("PATENT INFORMATION:\n")
                    f.write("-" * 40 + "\n")
                    for patent in patents:
                        f.write(f"Patent Number: {patent}\n")
                    f.write("\n")
                
                # 기술적 원리
                principle = invention_data.get('principle', '')
                if principle:
                    f.write("TECHNICAL PRINCIPLE:\n")
                    f.write("-" * 40 + "\n")
                    f.write(f"{principle}\n\n")
                
                # 상세 설명
                description = invention_data.get('description', '')
                if description:
                    f.write("DESCRIPTION:\n")
                    f.write("-" * 40 + "\n")
                    f.write(f"{description}\n\n")
                
                # 기술적 세부사항
                tech_details = invention_data.get('technical_details', [])
                if tech_details:
                    f.write("TECHNICAL DETAILS:\n")
                    f.write("-" * 40 + "\n")
                    for i, detail in enumerate(tech_details[:5], 1):  # 처음 5개만
                        f.write(f"{i}. {detail}\n\n")
                
                # 구조화된 섹션들
                sections = invention_data.get('structured_sections', {})
                if sections:
                    f.write("STRUCTURED SECTIONS:\n")
                    f.write("-" * 40 + "\n")
                    for section_title, content_list in sections.items():
                        f.write(f"\n[{section_title}]\n")
                        for content in content_list[:3]:  # 각 섹션당 3개까지
                            f.write(f"{content}\n")
                    f.write("\n")
                
                # 이미지 및 다이어그램 정보
                images = invention_data.get('images', [])
                diagrams = invention_data.get('diagrams', [])
                
                if images or diagrams:
                    f.write("VISUAL MATERIALS:\n")
                    f.write("-" * 40 + "\n")
                    
                    if diagrams:
                        f.write("Diagrams and Schematics:\n")
                        for i, diag in enumerate(diagrams, 1):
                            f.write(f"{i}. File: {diag['filename']}\n")
                            f.write(f"   URL: {diag['url']}\n")
                            if diag['alt_text']:
                                f.write(f"   Description: {diag['alt_text']}\n")
                            if diag['title']:
                                f.write(f"   Title: {diag['title']}\n")
                            f.write("\n")
                    
                    if images:
                        f.write("Images and Photos:\n")
                        for i, img in enumerate(images, 1):
                            f.write(f"{i}. File: {img['filename']}\n")
                            f.write(f"   URL: {img['url']}\n")
                            if img['alt_text']:
                                f.write(f"   Description: {img['alt_text']}\n")
                            if img['title']:
                                f.write(f"   Title: {img['title']}\n")
                            f.write("\n")
                
                # 참조 자료
                references = invention_data.get('references', [])
                if references:
                    f.write("REFERENCES:\n")
                    f.write("-" * 40 + "\n")
                    for i, ref in enumerate(references[:10], 1):  # 처음 10개만
                        f.write(f"{i}. {ref['text']}\n")
                        f.write(f"   URL: {ref['url']}\n\n")
                
                # 전체 컨텐츠 (LLM 학습용)
                f.write("FULL CONTENT FOR AI TRAINING:\n")
                f.write("-" * 40 + "\n")
                f.write(invention_data.get('full_content', ''))
                f.write("\n\n")
                
                # 메타데이터 (JSON 형식)
                f.write("METADATA (JSON):\n")
                f.write("-" * 40 + "\n")
                metadata = {
                    'name': invention_data.get('name'),
                    'title': invention_data.get('title'),
                    'url': invention_data.get('url'),
                    'patents': invention_data.get('patents'),
                    'image_count': len(invention_data.get('images', [])),
                    'diagram_count': len(invention_data.get('diagrams', [])),
                    'reference_count': len(invention_data.get('references', [])),
                    'extracted_at': invention_data.get('extracted_at')
                }
                f.write(json.dumps(metadata, indent=2, ensure_ascii=False))
            
            self.safe_log('info', f"💾 파일 저장 완료: {filepath}", f"[SAVE] 파일 저장 완료: {filepath}")
            return filepath
            
        except Exception as e:
            self.safe_log('error', f"❌ 파일 저장 실패: {filepath} - {e}", 
                         f"[ERROR] 파일 저장 실패: {filepath} - {e}")
            return None
    
    def crawl_invention_page(self, invention_info: Dict) -> Optional[Dict]:
        """개별 발명품 페이지 크롤링"""
        url = invention_info['url']
        name = invention_info['name']
        
        if url in self.visited_urls:
            return None
        
        self.visited_urls.add(url)
        
        soup = self.get_page(url)
        if not soup:
            return None
        
        invention_data = self.extract_invention_content(soup, url, name)
        invention_data['category'] = invention_info.get('category', 'general')
        
        return invention_data
    
    def run_crawler(self, max_pages: int = 0):
        """크롤링 실행"""
        self.safe_log('info', f"🚀 Rex Research 크롤링 시작: {self.base_url}", 
                     f"[START] Rex Research 크롤링 시작: {self.base_url}")
        
        # 출력 디렉토리 생성
        self.create_output_directory()
        
        # 메인 페이지 로드
        main_soup = self.get_page(self.base_url)
        if not main_soup:
            self.safe_log('error', "❌ 메인 페이지 로드 실패", "[ERROR] 메인 페이지 로드 실패")
            return None
        
        # 발명품 링크 추출
        invention_links = self.extract_invention_links(main_soup)
        
        if not invention_links:
            self.safe_log('warning', "⚠️ 발명품 링크를 찾을 수 없습니다", "[WARNING] 발명품 링크를 찾을 수 없습니다")
            return None
        
        # 전체 링크 수 로그
        total_found = len(invention_links)
        self.safe_log('info', f"📊 총 {total_found}개의 발명품 링크 발견!", 
                     f"[INFO] 총 {total_found}개의 발명품 링크 발견!")
        
        # 페이지 수 제한
        if max_pages > 0:
            invention_links = invention_links[:max_pages]
            self.safe_log('info', f"🔢 처음 {max_pages}개만 크롤링합니다", 
                         f"[LIMIT] 처음 {max_pages}개만 크롤링합니다")
        else:
            self.safe_log('info', f"🌟 전체 {total_found}개 발명품을 크롤링합니다!", 
                         f"[FULL] 전체 {total_found}개 발명품을 크롤링합니다!")
        
        self.safe_log('info', f"🚀 크롤링 시작 - 예상 소요시간: {self._estimate_time(len(invention_links))}분", 
                     f"[START] 크롤링 시작 - 예상 소요시간: {self._estimate_time(len(invention_links))}분")
        
        saved_files = []
        success_count = 0
        
        # 각 발명품 페이지 크롤링
        for i, invention_info in enumerate(invention_links, 1):
            clean_name = invention_info['name'][:50].replace('\n', ' ').strip()
            self.safe_log('info', f"🔄 진행상황: {i}/{len(invention_links)} - {clean_name}", 
                         f"[PROGRESS] {i}/{len(invention_links)} - {clean_name}")
            
            try:
                invention_data = self.crawl_invention_page(invention_info)
                if invention_data:
                    self.inventions_data.append(invention_data)
                    
                    # 개별 파일 저장
                    saved_file = self.save_invention_file(invention_data)
                    if saved_file:
                        saved_files.append(saved_file)
                        success_count += 1
                    
            except KeyboardInterrupt:
                self.safe_log('info', "⏹️ 사용자가 중단했습니다", "[STOP] 사용자가 중단했습니다")
                break
            except Exception as e:
                self.safe_log('error', f"❌ 크롤링 중 오류: {invention_info['name']} - {e}", 
                             f"[ERROR] 크롤링 중 오류: {invention_info['name']} - {e}")
                continue
        
        # 최종 결과
        result = {
            'total_links': len(invention_links),
            'successful_crawls': success_count,
            'saved_files': saved_files,
            'output_directory': self.output_dir,
            'failed_count': len(invention_links) - success_count
        }
        
        self.safe_log('info', f"✅ 크롤링 완료! 성공: {success_count}/{len(invention_links)}", 
                     f"[COMPLETE] 크롤링 완료! 성공: {success_count}/{len(invention_links)}")
        return result

# 사용 예시
if __name__ == "__main__":
    crawler = RexResearchCrawler()
    
    safe_print("🕷️ Rex Research 발명품 크롤러 시작", "Rex Research 발명품 크롤러 시작")
    safe_print("전체 발명품 크롤링을 시작합니다...")
    safe_print("⚠️ 대용량 크롤링입니다. 중단 시 Ctrl+C를 누르세요")
    
    result = crawler.run_crawler(max_pages=0)  # 전체 크롤링
    
    if result:
        safe_print(f"\n✅ 크롤링 결과:", "\n[RESULTS] 크롤링 결과:")
        safe_print(f"   - 총 링크 수: {result['total_links']}")
        safe_print(f"   - 성공적 크롤링: {result['successful_crawls']}")
        safe_print(f"   - 실패 수: {result['failed_count']}")
        safe_print(f"   - 저장된 파일: {len(result['saved_files'])}개")
        safe_print(f"   - 출력 디렉토리: {result['output_directory']}/")
        
        # 카테고리별 통계
        if crawler.inventions_data:
            categories = {}
            for invention in crawler.inventions_data:
                cat = invention.get('category', 'general')
                categories[cat] = categories.get(cat, 0) + 1
            
            safe_print(f"\n📊 카테고리별 통계:", "\n[CATEGORY STATS] 카테고리별 통계:")
            for cat, count in categories.items():
                safe_print(f"   - {cat}: {count}개")
    else:
        safe_print("❌ 크롤링에 실패했습니다.", "[ERROR] 크롤링에 실패했습니다.")

def safe_print(message_with_emoji, message_plain=""):
    """안전한 출력 (Windows 유니코드 호환)"""
    try:
        print(message_with_emoji)
    except UnicodeEncodeError:
        print(message_plain if message_plain else message_with_emoji.encode('ascii', 'ignore').decode('ascii'))