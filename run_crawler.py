import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from urllib.parse import urljoin, urlparse
import json
import csv
from datetime import datetime
import logging
from typing import Dict, List, Optional
import random

class RexResearchCrawler:
    def __init__(self, base_url: str = "https://www.rexresearch.com/invnindx.html"):
        self.base_url = base_url
        self.base_domain = "https://www.rexresearch.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # 로깅 설정
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('rex_research_crawler.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # 데이터 저장용 리스트
        self.inventors_data = []
        self.inventions_data = []
        
        # 방문한 URL 추적
        self.visited_urls = set()
        
        # 요청 간격 (초)
        self.request_delay = (1, 3)  # 1-3초 랜덤 지연
        
    def get_page(self, url: str, retries: int = 3) -> Optional[BeautifulSoup]:
        """페이지를 가져오고 BeautifulSoup 객체로 반환"""
        for attempt in range(retries):
            try:
                # 요청 지연
                time.sleep(random.uniform(*self.request_delay))
                
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                
                # 인코딩 처리
                if response.encoding is None:
                    response.encoding = 'utf-8'
                
                soup = BeautifulSoup(response.text, 'html.parser')
                self.logger.info(f"성공적으로 페이지 로드: {url}")
                return soup
                
            except requests.RequestException as e:
                self.logger.warning(f"페이지 로드 실패 (시도 {attempt + 1}/{retries}): {url} - {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # 지수 백오프
                    
        self.logger.error(f"모든 시도 실패: {url}")
        return None
    
    def extract_inventor_links(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """메인 페이지에서 발명자 링크들을 추출"""
        inventor_links = []
        
        # 일반적인 링크 패턴들을 찾기
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link.get('href')
            text = link.get_text(strip=True)
            
            if href and text:
                # 상대 URL을 절대 URL로 변환
                full_url = urljoin(self.base_domain, href)
                
                # 발명자/발명품 관련 링크 필터링
                if self.is_inventor_link(href, text):
                    inventor_links.append({
                        'name': text,
                        'url': full_url,
                        'href': href
                    })
        
        self.logger.info(f"총 {len(inventor_links)}개의 발명자 링크 발견")
        return inventor_links
    
    def is_inventor_link(self, href: str, text: str) -> bool:
        """링크가 발명자/발명품 관련인지 판단"""
        # 제외할 패턴들
        exclude_patterns = [
            'javascript:', 'mailto:', '#', 'http://', 'https://',
            'index.html', 'home.html', 'about.html'
        ]
        
        # 제외할 텍스트 패턴들
        exclude_texts = [
            'home', 'back', 'top', 'index', 'search', 'contact',
            'about', 'links', 'disclaimer'
        ]
        
        href_lower = href.lower()
        text_lower = text.lower()
        
        # 제외 패턴 체크
        for pattern in exclude_patterns:
            if pattern in href_lower:
                return False
        
        for pattern in exclude_texts:
            if pattern in text_lower:
                return False
        
        # HTML 파일이거나 발명자 이름 같은 패턴
        return (href.endswith('.html') or 
                len(text) > 2 and 
                not text.isdigit() and
                not text.startswith('['))
    
    def extract_inventor_data(self, soup: BeautifulSoup, url: str, name: str) -> Dict:
        """개별 발명자 페이지에서 데이터 추출"""
        inventor_data = {
            'name': name,
            'url': url,
            'extracted_at': datetime.now().isoformat(),
            'inventions': [],
            'biographical_info': '',
            'patents': [],
            'description': '',
            'images': [],
            'references': []
        }
        
        try:
            # 페이지 텍스트 전체 추출
            page_text = soup.get_text(separator=' ', strip=True)
            
            # 제목 추출
            title = soup.find('title')
            if title:
                inventor_data['page_title'] = title.get_text(strip=True)
            
            # 메타 정보 추출
            meta_description = soup.find('meta', {'name': 'description'})
            if meta_description:
                inventor_data['meta_description'] = meta_description.get('content', '')
            
            # 헤딩 태그들에서 발명품 정보 추출
            headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            for heading in headings:
                heading_text = heading.get_text(strip=True)
                if heading_text:
                    inventor_data['inventions'].append({
                        'title': heading_text,
                        'level': heading.name
                    })
            
            # 이미지 추출
            images = soup.find_all('img')
            for img in images:
                src = img.get('src')
                alt = img.get('alt', '')
                if src:
                    full_img_url = urljoin(url, src)
                    inventor_data['images'].append({
                        'url': full_img_url,
                        'alt': alt
                    })
            
            # 링크 추출 (참조 자료)
            links = soup.find_all('a', href=True)
            for link in links:
                href = link.get('href')
                text = link.get_text(strip=True)
                if href and text and href.startswith('http'):
                    inventor_data['references'].append({
                        'url': href,
                        'text': text
                    })
            
            # 특허 번호 패턴 찾기
            patent_patterns = [
                r'Patent\s+No\.?\s*(\d{1,2}[,.]?\d{3}[,.]?\d{3})',
                r'US\s*(\d{1,2}[,.]?\d{3}[,.]?\d{3})',
                r'Patent\s+#\s*(\d{1,2}[,.]?\d{3}[,.]?\d{3})'
            ]
            
            for pattern in patent_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                for match in matches:
                    inventor_data['patents'].append(match.replace(',', '').replace('.', ''))
            
            # 설명 텍스트 추출 (첫 1000자)
            inventor_data['description'] = page_text[:1000] if page_text else ''
            
            # 전체 텍스트 저장
            inventor_data['full_text'] = page_text[:5000]  # 처음 5000자만 저장
            
        except Exception as e:
            self.logger.error(f"데이터 추출 중 오류 발생: {url} - {e}")
        
        return inventor_data
    
    def crawl_inventor_page(self, inventor_info: Dict) -> Optional[Dict]:
        """개별 발명자 페이지 크롤링"""
        url = inventor_info['url']
        name = inventor_info['name']
        
        if url in self.visited_urls:
            return None
        
        self.visited_urls.add(url)
        
        soup = self.get_page(url)
        if not soup:
            return None
        
        inventor_data = self.extract_inventor_data(soup, url, name)
        return inventor_data
    
    def save_data(self, filename_prefix: str = "rex_research_data"):
        """데이터를 다양한 형식으로 저장"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # JSON 저장
        json_filename = f"{filename_prefix}_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump({
                'inventors': self.inventors_data,
                'crawl_info': {
                    'total_inventors': len(self.inventors_data),
                    'crawl_date': datetime.now().isoformat(),
                    'base_url': self.base_url
                }
            }, f, ensure_ascii=False, indent=2)
        
        # CSV 저장 (기본 정보)
        csv_filename = f"{filename_prefix}_{timestamp}.csv"
        if self.inventors_data:
            # 플랫 데이터 준비
            flat_data = []
            for inventor in self.inventors_data:
                flat_record = {
                    'name': inventor.get('name', ''),
                    'url': inventor.get('url', ''),
                    'page_title': inventor.get('page_title', ''),
                    'description': inventor.get('description', ''),
                    'patent_count': len(inventor.get('patents', [])),
                    'patents': ', '.join(inventor.get('patents', [])),
                    'invention_count': len(inventor.get('inventions', [])),
                    'image_count': len(inventor.get('images', [])),
                    'reference_count': len(inventor.get('references', [])),
                    'extracted_at': inventor.get('extracted_at', '')
                }
                flat_data.append(flat_record)
            
            df = pd.DataFrame(flat_data)
            df.to_csv(csv_filename, index=False, encoding='utf-8')
        
        # 상세 발명품 정보 CSV
        inventions_filename = f"{filename_prefix}_inventions_{timestamp}.csv"
        inventions_flat = []
        for inventor in self.inventors_data:
            inventor_name = inventor.get('name', '')
            for invention in inventor.get('inventions', []):
                inventions_flat.append({
                    'inventor_name': inventor_name,
                    'invention_title': invention.get('title', ''),
                    'heading_level': invention.get('level', ''),
                    'inventor_url': inventor.get('url', '')
                })
        
        if inventions_flat:
            df_inventions = pd.DataFrame(inventions_flat)
            df_inventions.to_csv(inventions_filename, index=False, encoding='utf-8')
        
        self.logger.info(f"데이터 저장 완료:")
        self.logger.info(f"- JSON: {json_filename}")
        self.logger.info(f"- CSV: {csv_filename}")
        self.logger.info(f"- 발명품 CSV: {inventions_filename}")
        
        return {
            'json_file': json_filename,
            'csv_file': csv_filename,
            'inventions_file': inventions_filename
        }
    
    def run_crawler(self, max_pages: int = 100):
        """크롤링 실행"""
        self.logger.info(f"크롤링 시작: {self.base_url}")
        
        # 메인 페이지 로드
        main_soup = self.get_page(self.base_url)
        if not main_soup:
            self.logger.error("메인 페이지 로드 실패")
            return
        
        # 발명자 링크 추출
        inventor_links = self.extract_inventor_links(main_soup)
        
        if not inventor_links:
            self.logger.warning("발명자 링크를 찾을 수 없습니다")
            return
        
        # 페이지 수 제한
        inventor_links = inventor_links[:max_pages]
        
        self.logger.info(f"총 {len(inventor_links)}개 페이지 크롤링 시작")
        
        # 각 발명자 페이지 크롤링
        for i, inventor_info in enumerate(inventor_links, 1):
            self.logger.info(f"진행상황: {i}/{len(inventor_links)} - {inventor_info['name']}")
            
            try:
                inventor_data = self.crawl_inventor_page(inventor_info)
                if inventor_data:
                    self.inventors_data.append(inventor_data)
                    
            except Exception as e:
                self.logger.error(f"크롤링 중 오류: {inventor_info['name']} - {e}")
                continue
        
        # 결과 저장
        if self.inventors_data:
            saved_files = self.save_data()
            self.logger.info(f"크롤링 완료! 총 {len(self.inventors_data)}개 발명자 데이터 수집")
            return saved_files
        else:
            self.logger.warning("수집된 데이터가 없습니다")
            return None

# 사용 예시
if __name__ == "__main__":
    # 크롤러 인스턴스 생성
    crawler = RexResearchCrawler()
    
    # 크롤링 실행 (최대 50페이지)
    print("Rex Research 크롤링을 시작합니다...")
    result = crawler.run_crawler(max_pages=50)
    
    if result:
        print(f"\n크롤링 완료!")
        print(f"저장된 파일들:")
        for file_type, filename in result.items():
            print(f"- {file_type}: {filename}")
    else:
        print("크롤링에 실패했습니다.")
    
    # 간단한 통계 출력
    if crawler.inventors_data:
        print(f"\n=== 크롤링 통계 ===")
        print(f"총 발명자 수: {len(crawler.inventors_data)}")
        
        total_inventions = sum(len(inv.get('inventions', [])) for inv in crawler.inventors_data)
        print(f"총 발명품 수: {total_inventions}")
        
        total_patents = sum(len(inv.get('patents', [])) for inv in crawler.inventors_data)
        print(f"총 특허 수: {total_patents}")
        
        total_images = sum(len(inv.get('images', [])) for inv in crawler.inventors_data)
        print(f"총 이미지 수: {total_images}")
        
        # 상위 5개 발명자 (발명품 수 기준)
        top_inventors = sorted(crawler.inventors_data, 
                             key=lambda x: len(x.get('inventions', [])), 
                             reverse=True)[:5]
        
        print(f"\n=== 상위 5개 발명자 (발명품 수) ===")
        for i, inventor in enumerate(top_inventors, 1):
            print(f"{i}. {inventor.get('name', 'Unknown')} - "
                  f"{len(inventor.get('inventions', []))}개 발명품")