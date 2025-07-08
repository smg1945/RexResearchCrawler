#!/usr/bin/env python3
"""
Rex Research 발명품 크롤러 - 한 링크당 하나의 LLM 학습용 파일 생성
사용법: python main.py [옵션]
"""

import argparse
import sys
import os
from run_crawler import RexResearchCrawler

def safe_print(message_with_emoji, message_plain=""):
    """안전한 출력 (Windows 유니코드 호환)"""
    try:
        print(message_with_emoji)
    except UnicodeEncodeError:
        print(message_plain if message_plain else message_with_emoji.encode('ascii', 'ignore').decode('ascii'))

def main():
    # Windows 콘솔 인코딩 설정
    import sys
    if sys.platform == "win32":
        try:
            import os
            os.system('chcp 65001 > nul')  # UTF-8 코드페이지 설정
        except:
            pass
    
    parser = argparse.ArgumentParser(
        description='Rex Research 발명품 크롤러 - 각 발명품별 개별 LLM 학습용 파일 생성',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
🎯 목적: 각 발명품 링크별로 원리와 설명을 포함한 개별 파일 생성

사용 예시:
  python main.py                           # 기본 설정으로 50개 발명품 크롤링
  python main.py -n 20                     # 20개 발명품만 크롤링
  python main.py -d 2 5                    # 2-5초 지연으로 크롤링
  python main.py -o inventions_data        # 출력 디렉토리명 지정
  python main.py --verbose                 # 상세 로그 출력
  python main.py --test                    # 처음 5개만 테스트
  python main.py --category energy         # 특정 카테고리만 크롤링
        """
    )
    
    parser.add_argument(
        '-n', '--max-pages',
        type=int,
        default=0,
        help='크롤링할 최대 발명품 수 (기본값: 0=전체, 테스트용으로 50 등 지정 가능)'
    )
    
    parser.add_argument(
        '-d', '--delay',
        nargs=2,
        type=float,
        default=[1.0, 3.0],
        metavar=('MIN', 'MAX'),
        help='요청 간 지연 시간 범위 (초) (기본값: 1.0 3.0)'
    )
    
    parser.add_argument(
        '-o', '--output-dir',
        type=str,
        default='rex_inventions',
        help='출력 디렉토리명 (기본값: rex_inventions)'
    )
    
    parser.add_argument(
        '--url',
        type=str,
        default='https://www.rexresearch.com/invnindx.html',
        help='크롤링할 기본 URL'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='상세 로그 출력'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='실제 크롤링 없이 링크만 확인'
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='테스트 모드 (처음 5개만 크롤링)'
    )
    
    parser.add_argument(
        '--category',
        type=str,
        choices=['energy', 'medical', 'transport', 'general'],
        help='특정 카테고리만 크롤링'
    )
    
    parser.add_argument(
        '--resume',
        action='store_true',
        help='기존 파일이 있으면 건너뛰고 계속'
    )
    
    args = parser.parse_args()
    
    # 테스트 모드
    if args.test:
        args.max_pages = 5
        safe_print("🧪 테스트 모드: 처음 5개 발명품만 크롤링합니다", "[TEST] 테스트 모드: 처음 5개 발명품만 크롤링합니다")
    
    # 로깅 레벨 설정
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    safe_print("=" * 80)
    safe_print("🕷️  Rex Research 발명품 크롤러", "Rex Research 발명품 크롤러")
    safe_print("🎯  목적: 한 링크당 하나의 LLM 학습용 파일 생성", "목적: 한 링크당 하나의 LLM 학습용 파일 생성")
    safe_print("=" * 80)
    safe_print(f"📋 설정:", "설정:")
    safe_print(f"   - 최대 발명품 수: {args.max_pages if args.max_pages > 0 else '전체 (1000개 이상 예상)'}")
    safe_print(f"   - 요청 지연: {args.delay[0]}-{args.delay[1]}초")
    safe_print(f"   - 출력 디렉토리: {args.output_dir}/")
    safe_print(f"   - 기본 URL: {args.url}")
    safe_print(f"   - Dry Run: {'예' if args.dry_run else '아니오'}")
    safe_print(f"   - 카테고리 필터: {args.category if args.category else '전체'}")
    safe_print(f"   - 재시작 모드: {'예' if args.resume else '아니오'}")
    safe_print("=" * 80)
    
    # 전체 크롤링 경고
    if args.max_pages == 0 and not args.dry_run and not args.test:
        safe_print("\n⚠️  전체 크롤링 모드입니다!", "[WARNING] 전체 크롤링 모드입니다!")
        safe_print("   - 예상 소요시간: 2-6시간 (1000개 이상)")
        safe_print("   - 권장사항: 먼저 --test 또는 --dry-run으로 확인")
        safe_print("   - 중단 시 Ctrl+C, 재시작 시 --resume 사용")
        safe_print("\n계속하시려면 Enter를 누르세요 (Ctrl+C로 취소)")
        try:
            input()
        except KeyboardInterrupt:
            safe_print("\n취소되었습니다.")
            return
    
    try:
        # 크롤러 생성 및 설정
        crawler = RexResearchCrawler(base_url=args.url)
        crawler.request_delay = tuple(args.delay)
        crawler.output_dir = args.output_dir
        
        if args.dry_run:
            safe_print("🔍 Dry Run 모드: 링크만 확인합니다...", "[DRY RUN] 링크만 확인합니다...")
            main_soup = crawler.get_page(args.url)
            if main_soup:
                links = crawler.extract_invention_links(main_soup)
                safe_print(f"✅ 총 {len(links)}개의 발명품 링크 발견", f"[SUCCESS] 총 {len(links)}개의 발명품 링크 발견")
                
                # 카테고리별 분석
                categories = {}
                for link in links:
                    cat = link.get('category', 'general')
                    categories[cat] = categories.get(cat, 0) + 1
                
                safe_print(f"\n📊 카테고리별 분포:", "\n[STATS] 카테고리별 분포:")
                for cat, count in categories.items():
                    safe_print(f"   - {cat}: {count}개")
                
                safe_print(f"\n📝 발견된 링크들 (처음 10개):", "\n[LINKS] 발견된 링크들 (처음 10개):")
                display_links = links[:10]
                if args.category:
                    display_links = [link for link in links if link['category'] == args.category][:10]
                
                for i, link in enumerate(display_links, 1):
                    safe_print(f"   {i:2d}. [{link['category']:8}] {link['name'][:60]}")
                
                if len(links) > 10:
                    remaining = len(links) - 10
                    if args.category:
                        remaining = len([l for l in links if l['category'] == args.category]) - 10
                    if remaining > 0:
                        safe_print(f"   ... 그리고 {remaining}개 더")
            else:
                safe_print("❌ 메인 페이지를 불러올 수 없습니다.", "[ERROR] 메인 페이지를 불러올 수 없습니다.")
            return
        
        # 실제 크롤링 실행
        safe_print("🚀 발명품 크롤링을 시작합니다...", "[START] 발명품 크롤링을 시작합니다...")
        safe_print("📄 각 발명품별로 개별 파일을 생성합니다...", "[INFO] 각 발명품별로 개별 파일을 생성합니다...")
        
        result = crawler.run_crawler(max_pages=args.max_pages)
        
        if result:
            safe_print("\n✅ 크롤링 완료!", "\n[COMPLETE] 크롤링 완료!")
            safe_print(f"📊 수집 결과:", "[RESULTS] 수집 결과:")
            safe_print(f"   - 총 링크 수: {result['total_links']}")
            safe_print(f"   - 성공적 크롤링: {result['successful_crawls']}")
            safe_print(f"   - 실패 수: {result['failed_count']}")
            safe_print(f"   - 생성된 파일: {len(result['saved_files'])}개")
            
            # 성공률 계산
            success_rate = (result['successful_crawls'] / result['total_links']) * 100
            safe_print(f"   - 성공률: {success_rate:.1f}%")
            
            # 디렉토리 정보
            safe_print(f"\n📁 출력 정보:", "\n[OUTPUT] 출력 정보:")
            safe_print(f"   - 출력 디렉토리: {result['output_directory']}/")
            
            # 디렉토리 크기 계산
            total_size = 0
            file_count = 0
            if os.path.exists(result['output_directory']):
                for filename in os.listdir(result['output_directory']):
                    filepath = os.path.join(result['output_directory'], filename)
                    if os.path.isfile(filepath):
                        total_size += os.path.getsize(filepath)
                        file_count += 1
                
                total_size_mb = total_size / (1024 * 1024)
                safe_print(f"   - 총 파일 크기: {total_size_mb:.2f} MB")
                safe_print(f"   - 파일 개수: {file_count}개")
                safe_print(f"   - 평균 파일 크기: {(total_size_mb / file_count) if file_count > 0 else 0:.2f} MB")
            
            # 카테고리별 통계
            if crawler.inventions_data:
                categories = {}
                patents_total = 0
                images_total = 0
                
                for invention in crawler.inventions_data:
                    cat = invention.get('category', 'general')
                    categories[cat] = categories.get(cat, 0) + 1
                    patents_total += len(invention.get('patents', []))
                    images_total += len(invention.get('images', [])) + len(invention.get('diagrams', []))
                
                safe_print(f"\n📊 상세 통계:", "\n[DETAILED STATS] 상세 통계:")
                safe_print(f"   - 총 특허 수: {patents_total}")
                safe_print(f"   - 총 이미지 수: {images_total}")
                
                safe_print(f"\n🏷️ 카테고리별 분포:", "\n[CATEGORY] 카테고리별 분포:")
                for cat, count in sorted(categories.items()):
                    percentage = (count / len(crawler.inventions_data)) * 100
                    safe_print(f"   - {cat:10}: {count:3d}개 ({percentage:5.1f}%)")
                
                # 상위 발명품 (내용 길이 기준)
                sorted_inventions = sorted(
                    crawler.inventions_data,
                    key=lambda x: len(x.get('full_content', '')),
                    reverse=True
                )[:5]
                
                safe_print(f"\n🏆 상위 5개 발명품 (내용 길이):", "\n[TOP 5] 상위 5개 발명품 (내용 길이):")
                for i, inv in enumerate(sorted_inventions, 1):
                    content_length = len(inv.get('full_content', ''))
                    patent_count = len(inv.get('patents', []))
                    image_count = len(inv.get('images', [])) + len(inv.get('diagrams', []))
                    safe_print(f"   {i}. {inv.get('name', 'Unknown')[:50]:<50}")
                    safe_print(f"      길이: {content_length:,}자, 특허: {patent_count}개, 이미지: {image_count}개")
            
            # LLM 학습 관련 정보
            safe_print(f"\n🤖 LLM 학습용 데이터 정보:", "\n[AI DATA] LLM 학습용 데이터 정보:")
            safe_print(f"   - 각 파일은 구조화된 텍스트 형식")
            safe_print(f"   - 포함 정보: 발명 원리, 기술 설명, 특허, 이미지 정보")
            safe_print(f"   - 파일 형식: UTF-8 텍스트 (.txt)")
            safe_print(f"   - 디렉토리: {result['output_directory']}/")
            
            # 사용 권장사항
            safe_print(f"\n💡 사용 권장사항:", "\n[TIPS] 사용 권장사항:")
            safe_print(f"   📚 개별 학습: 각 .txt 파일을 별도 문서로 처리", "   개별 학습: 각 .txt 파일을 별도 문서로 처리")
            safe_print(f"   🔍 키워드 검색: 파일명으로 특정 발명품 찾기", "   키워드 검색: 파일명으로 특정 발명품 찾기")
            safe_print(f"   📊 배치 처리: 전체 디렉토리를 한번에 로드", "   배치 처리: 전체 디렉토리를 한번에 로드")
            safe_print(f"   🏷️ 카테고리별: 파일 내 메타데이터로 분류 가능", "   카테고리별: 파일 내 메타데이터로 분류 가능")
            
        else:
            safe_print("❌ 크롤링에 실패했습니다.", "[ERROR] 크롤링에 실패했습니다.")
            safe_print("📋 로그 파일(rex_research_crawler.log)을 확인해주세요.", "[INFO] 로그 파일(rex_research_crawler.log)을 확인해주세요.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        safe_print("\n\n⏹️  사용자에 의해 중단되었습니다.", "\n\n[STOP] 사용자에 의해 중단되었습니다.")
        if hasattr(crawler, 'inventions_data') and crawler.inventions_data:
            safe_print("💾 수집된 데이터를 확인하는 중...", "[INFO] 수집된 데이터를 확인하는 중...")
            safe_print(f"   - 수집된 발명품: {len(crawler.inventions_data)}개")
            
            # 기존 저장된 파일 확인
            if os.path.exists(crawler.output_dir):
                existing_files = [f for f in os.listdir(crawler.output_dir) if f.endswith('.txt')]
                safe_print(f"   - 저장된 파일: {len(existing_files)}개")
                safe_print(f"   - 출력 디렉토리: {crawler.output_dir}/")
        sys.exit(0)
        
    except Exception as e:
        safe_print(f"❌ 예상치 못한 오류 발생: {e}", f"[ERROR] 예상치 못한 오류 발생: {e}")
        safe_print("📋 로그 파일(rex_research_crawler.log)을 확인해주세요.", "[INFO] 로그 파일(rex_research_crawler.log)을 확인해주세요.")
        import traceback
        if args.verbose:
            safe_print("\n상세 오류 정보:")
            traceback.print_exc()
        sys.exit(1)

def display_usage_examples():
    """사용 예시 표시"""
    safe_print("\n" + "=" * 80)
    safe_print("📖 Rex Research 발명품 크롤러 사용 가이드", "[GUIDE] Rex Research 발명품 크롤러 사용 가이드")
    safe_print("=" * 80)
    
    safe_print("\n🎯 목적:", "\n[PURPOSE] 목적:")
    safe_print("   - Rex Research 웹사이트의 각 발명품 링크별로")
    safe_print("   - 발명 원리, 기술 설명, 이미지 정보를 포함한")
    safe_print("   - LLM 학습용 개별 텍스트 파일 생성")
    
    safe_print("\n📝 사용 예시:", "\n[EXAMPLES] 사용 예시:")
    examples = [
        ("전체 크롤링 (1000개+)", "python main.py"),
        ("소규모 테스트 (5개)", "python main.py --test"),
        ("일부만 크롤링 (100개)", "python main.py -n 100"),
        ("빠른 크롤링", "python main.py -d 0.5 1.0"),
        ("에너지 분야만", "python main.py --category energy"),
        ("링크만 확인", "python main.py --dry-run"),
        ("상세 로그", "python main.py --verbose"),
        ("재시작 모드", "python main.py --resume")
    ]
    
    for desc, cmd in examples:
        safe_print(f"   {desc:<20}: {cmd}")
    
    safe_print("\n📊 출력 파일 구조:", "\n[STRUCTURE] 출력 파일 구조:")
    safe_print("   rex_inventions/")
    safe_print("   ├── INVENTION_NAME_1.txt")
    safe_print("   ├── INVENTION_NAME_2.txt")
    safe_print("   └── ...")
    
    safe_print("\n📄 각 파일 내용:", "\n[CONTENT] 각 파일 내용:")
    safe_print("   - 발명품 기본 정보")
    safe_print("   - 기술적 원리 설명")
    safe_print("   - 상세 기술 정보")
    safe_print("   - 특허 번호")
    safe_print("   - 이미지/다이어그램 정보")
    safe_print("   - 참조 자료")
    safe_print("   - 전체 원문 텍스트")
    safe_print("   - JSON 메타데이터")
    
    safe_print("\n⚠️ 주의사항:", "\n[WARNING] 주의사항:")
    safe_print("   - 웹사이트에 부하를 주지 않도록 적절한 지연 시간 사용")
    safe_print("   - 대량 크롤링 시 --resume 옵션으로 중단 시점부터 재시작")
    safe_print("   - 테스트 후 본격적인 크롤링 권장")
    
    safe_print("=" * 80)

def check_requirements():
    """필요한 패키지 확인"""
    required_packages = ['requests', 'beautifulsoup4']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package if package != 'beautifulsoup4' else 'bs4')
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        safe_print("❌ 필요한 패키지가 설치되지 않았습니다:", "[ERROR] 필요한 패키지가 설치되지 않았습니다:")
        for package in missing_packages:
            safe_print(f"   - {package}")
        safe_print("\n설치 명령어:")
        safe_print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

if __name__ == "__main__":
    # 패키지 확인
    if not check_requirements():
        sys.exit(1)
    
    # 인자 없이 실행 시 사용법 표시
    if len(sys.argv) == 1:
        display_usage_examples()
        safe_print("\n자세한 옵션은 'python main.py --help'를 실행하세요.")
        safe_print("기본 설정으로 크롤링을 시작하려면 Enter를 누르세요 (Ctrl+C로 취소)")
        try:
            input()
        except KeyboardInterrupt:
            safe_print("\n취소되었습니다.")
            sys.exit(0)
    
    main()