#!/usr/bin/env python3
"""
Rex Research 크롤러 간단 실행 스크립트
사용법: python run_crawler.py [옵션]
"""

import argparse
import sys
import os
from run_crawler import RexResearchCrawler

def main():
    parser = argparse.ArgumentParser(
        description='Rex Research 웹사이트 크롤링 프로그램',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python run_crawler.py                    # 기본 설정으로 50페이지 크롤링
  python run_crawler.py -n 20              # 20페이지만 크롤링
  python run_crawler.py -d 2 5             # 2-5초 지연으로 크롤링
  python run_crawler.py -o my_data         # 출력 파일명 지정
  python run_crawler.py --verbose          # 상세 로그 출력
        """
    )
    
    parser.add_argument(
        '-n', '--max-pages',
        type=int,
        default=50,
        help='크롤링할 최대 페이지 수 (기본값: 50)'
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
        '-o', '--output',
        type=str,
        default='rex_research_data',
        help='출력 파일명 접두사 (기본값: rex_research_data)'
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
    
    args = parser.parse_args()
    
    # 로깅 레벨 설정
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    print("=" * 60)
    print("🕷️  Rex Research 크롤러")
    print("=" * 60)
    print(f"📋 설정:")
    print(f"   - 최대 페이지: {args.max_pages}")
    print(f"   - 요청 지연: {args.delay[0]}-{args.delay[1]}초")
    print(f"   - 출력 파일: {args.output}_*.csv/json")
    print(f"   - 기본 URL: {args.url}")
    print(f"   - Dry Run: {'예' if args.dry_run else '아니오'}")
    print("=" * 60)
    
    try:
        # 크롤러 생성 및 설정
        crawler = RexResearchCrawler(base_url=args.url)
        crawler.request_delay = tuple(args.delay)
        
        if args.dry_run:
            print("🔍 Dry Run 모드: 링크만 확인합니다...")
            main_soup = crawler.get_page(args.url)
            if main_soup:
                links = crawler.extract_inventor_links(main_soup)
                print(f"✅ 총 {len(links)}개의 발명자 링크 발견")
                
                print("\n📝 발견된 링크들 (처음 10개):")
                for i, link in enumerate(links[:10], 1):
                    print(f"   {i:2d}. {link['name'][:50]:<50} -> {link['href']}")
                
                if len(links) > 10:
                    print(f"   ... 그리고 {len(links) - 10}개 더")
            else:
                print("❌ 메인 페이지를 불러올 수 없습니다.")
            return
        
        # 실제 크롤링 실행
        print("🚀 크롤링을 시작합니다...")
        result = crawler.run_crawler(max_pages=args.max_pages)
        
        if result:
            print("\n✅ 크롤링 완료!")
            print(f"📊 수집 결과:")
            print(f"   - 발명자 수: {len(crawler.inventors_data)}")
            
            total_inventions = sum(len(inv.get('inventions', [])) for inv in crawler.inventors_data)
            total_patents = sum(len(inv.get('patents', [])) for inv in crawler.inventors_data)
            total_images = sum(len(inv.get('images', [])) for inv in crawler.inventors_data)
            
            print(f"   - 발명품 수: {total_inventions}")
            print(f"   - 특허 수: {total_patents}")
            print(f"   - 이미지 수: {total_images}")
            
            print(f"\n📁 저장된 파일:")
            for file_type, filename in result.items():
                file_size = os.path.getsize(filename) / 1024  # KB 단위
                print(f"   - {filename} ({file_size:.1f} KB)")
            
            # 상위 발명자 표시
            if crawler.inventors_data:
                top_inventors = sorted(
                    crawler.inventors_data,
                    key=lambda x: len(x.get('inventions', [])),
                    reverse=True
                )[:5]
                
                print(f"\n🏆 상위 5개 발명자 (발명품 수):")
                for i, inventor in enumerate(top_inventors, 1):
                    inv_count = len(inventor.get('inventions', []))
                    pat_count = len(inventor.get('patents', []))
                    print(f"   {i}. {inventor.get('name', 'Unknown')[:40]:<40} "
                          f"발명품: {inv_count:2d}, 특허: {pat_count:2d}")
        else:
            print("❌ 크롤링에 실패했습니다.")
            print("📋 로그 파일(rex_research_crawler.log)을 확인해주세요.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  사용자에 의해 중단되었습니다.")
        if hasattr(crawler, 'inventors_data') and crawler.inventors_data:
            print("💾 수집된 데이터를 저장합니다...")
            try:
                result = crawler.save_data(args.output + "_interrupted")
                print(f"✅ 부분 데이터 저장 완료: {result}")
            except Exception as e:
                print(f"❌ 데이터 저장 실패: {e}")
        sys.exit(0)
        
    except Exception as e:
        print(f"❌ 예상치 못한 오류 발생: {e}")
        print("📋 로그 파일(rex_research_crawler.log)을 확인해주세요.")
        sys.exit(1)

if __name__ == "__main__":
    main()