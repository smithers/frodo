import re
import random
from datetime import datetime

from django.contrib.auth.models import User

from .models import UserFavoriteBook, Book


def smart_title_case(text: str) -> str:
    """
    Title-case helper that avoids capital 'S' after apostrophes.
    Example: "ender's game" -> "Ender's Game" (not "Ender'S Game")
    Handles both regular apostrophes (') and curly apostrophes (')
    """
    if not text:
        return text
    titled = text.strip().title()
    # Replace capital S after any type of apostrophe with lowercase s
    # Handles regular apostrophe (') and curly apostrophes (' and ')
    # First handle curly apostrophes (U+2019, U+2018)
    titled = titled.replace(chr(8217) + "S", "'s")  # Right single quotation mark
    titled = titled.replace(chr(8216) + "S", "'s")  # Left single quotation mark
    # Then handle regular apostrophe
    return re.sub(r"'S\b", "'s", titled)


def get_book_recommendations(current_user):
    # 1. Find books I love (favorites)
    my_favorite_ids = set(
        UserFavoriteBook.objects.filter(
            user=current_user,
        ).values_list("book_id", flat=True)
    )

    if not my_favorite_ids:
        return []

    # 2. Find other users who also love at least one of those same books
    similar_users = (
        User.objects.filter(
            favorite_books__book_id__in=my_favorite_ids,
        )
        .exclude(id=current_user.id)
        .distinct()
    )

    # 3. For each recommended book, track which similar user(s) recommended it
    # and count the overlap in favorite books
    book_recommendations = {}  # book_id -> {book, similar_user, overlap_count}
    
    my_favorite_books = set(
        UserFavoriteBook.objects.filter(user=current_user).values_list("book_id", flat=True)
    )

    for user in similar_users:
        # Get all books this user loves
        their_favorite_book_ids = set(
            UserFavoriteBook.objects.filter(
                user=user
            ).values_list("book_id", flat=True)
        )
        
        # Find overlapping books: books BOTH users love
        overlapping_book_ids = my_favorite_books & their_favorite_book_ids
        overlap_count = len(overlapping_book_ids)
        
        # Get the actual Book objects for overlapping favorites
        overlapping_books = Book.objects.filter(id__in=overlapping_book_ids)
        overlapping_titles = [book.title for book in overlapping_books]
        
        # For each book they love that I haven't favorited, add it as a recommendation
        for book_id in their_favorite_book_ids:
            if book_id not in my_favorite_books:
                # If we haven't seen this book yet, or if this user has more overlap, use this user
                if book_id not in book_recommendations or overlap_count > book_recommendations[book_id]['overlap_count']:
                    book_recommendations[book_id] = {
                        'book_id': book_id,
                        'similar_user': user,
                        'overlap_count': overlap_count,
                        'overlapping_titles': overlapping_titles,
                    }

    # Convert to list of dictionaries with book objects
    result = []
    for rec_data in book_recommendations.values():
        book = Book.objects.get(id=rec_data['book_id'])
        result.append({
            'book': book,
            'similar_user': rec_data['similar_user'],
            'overlap_count': rec_data['overlap_count'],
            'overlapping_titles': rec_data['overlapping_titles'],
        })
    
    # Sort by overlap_count (descending) - users with more overlapping favorites first
    result.sort(key=lambda x: x['overlap_count'], reverse=True)
    
    return result


def generate_guest_username():
    """
    Generate a unique username for guest users (max 12 characters) in the format:
    _DD + animal_abbrev + area_code + team_abbrev
    Example: _19Ti415Wa (underscore prefix, day 19, Tiger, area 415, Warriors)
    """
    # Date component (day of month only, 1-31, so 1-2 digits)
    day = str(datetime.now().day)
    
    # Animals with 2-letter abbreviations
    animals = {
        "Tiger": "Ti", "Lion": "Li", "Eagle": "Ea", "Bear": "Be", "Wolf": "Wo",
        "Fox": "Fx", "Hawk": "Hw", "Falcon": "Fa", "Panther": "Pa", "Jaguar": "Ja",
        "Leopard": "Le", "Lynx": "Lx", "Bobcat": "Bo", "Cougar": "Co", "Puma": "Pu",
        "Cheetah": "Ch", "Owl": "Ow", "Raven": "Ra", "Crow": "Cr", "Shark": "Sh",
        "Dolphin": "Do", "Whale": "Wh", "Seal": "Se", "Otter": "Ot", "Beaver": "Bv",
        "Moose": "Mo", "Elk": "Ek", "Deer": "Dr", "Stag": "St", "Ram": "Rm",
        "Goat": "Gt", "Sheep": "Sp", "Bull": "Bl", "Stallion": "Sl", "Mustang": "Mg",
        "Colt": "Ct", "Pony": "Py", "Zebra": "Zb", "Giraffe": "Gf", "Elephant": "El",
        "Rhino": "Rh", "Hippo": "Hp", "Crocodile": "Cd", "Alligator": "Al", "Turtle": "Tu",
        "Tortoise": "To", "Snake": "Sn", "Python": "Py", "Cobra": "Cb", "Viper": "Vp",
        "Dragon": "Dg", "Griffin": "Gf", "Phoenix": "Ph", "Unicorn": "Un"
    }
    
    # Area codes (popular US area codes)
    area_codes = [
        "212", "213", "214", "215", "216", "217", "218", "219", "224", "225",
        "226", "228", "229", "231", "234", "239", "240", "248", "251", "252",
        "253", "254", "256", "260", "262", "267", "269", "270", "272", "274",
        "276", "281", "283", "301", "302", "303", "304", "305", "307", "308",
        "309", "310", "312", "313", "314", "315", "316", "317", "318", "319",
        "320", "321", "323", "325", "327", "330", "331", "332", "334", "336",
        "337", "339", "341", "346", "347", "351", "352", "360", "361", "364",
        "380", "385", "386", "401", "402", "403", "404", "405", "406", "407",
        "408", "409", "410", "412", "413", "414", "415", "417", "418", "419",
        "423", "424", "425", "430", "432", "434", "435", "440", "442", "443",
        "445", "447", "448", "458", "463", "464", "469", "470", "475", "478",
        "479", "480", "484", "501", "502", "503", "504", "505", "507", "508",
        "509", "510", "512", "513", "515", "516", "517", "518", "520", "530",
        "531", "534", "539", "540", "541", "551", "559", "561", "562", "563",
        "564", "567", "570", "571", "572", "573", "574", "575", "580", "585",
        "586", "601", "602", "603", "605", "606", "607", "608", "609", "610",
        "612", "614", "615", "616", "617", "618", "619", "620", "623", "626",
        "628", "629", "630", "631", "636", "641", "646", "647", "650", "651",
        "657", "659", "660", "661", "662", "667", "669", "670", "671", "672",
        "678", "679", "680", "681", "682", "684", "689", "701", "702", "703",
        "704", "706", "707", "708", "712", "713", "714", "715", "716", "717",
        "718", "719", "720", "721", "724", "725", "726", "727", "728", "730",
        "731", "732", "734", "737", "740", "743", "747", "754", "757", "760",
        "762", "763", "764", "765", "769", "770", "771", "772", "773", "774",
        "775", "779", "781", "785", "786", "787", "801", "802", "803", "804",
        "805", "806", "807", "808", "810", "812", "813", "814", "815", "816",
        "817", "818", "828", "830", "831", "832", "843", "845", "847", "848",
        "850", "854", "856", "857", "858", "859", "860", "862", "863", "864",
        "865", "870", "872", "878", "901", "903", "904", "906", "907", "908",
        "909", "910", "912", "913", "914", "915", "916", "917", "918", "919",
        "920", "925", "928", "929", "930", "931", "934", "936", "937", "938",
        "940", "941", "947", "949", "951", "952", "954", "956", "959", "970",
        "971", "972", "973", "975", "978", "979", "980", "984", "985", "989"
    ]
    
    # Professional sports teams with 2-letter abbreviations
    sports_teams = {
        # NFL
        "Patriots": "Pt", "Jets": "Jt", "Giants": "Gt", "Eagles": "Eg", "Cowboys": "Cw",
        "Commanders": "Cm", "Bears": "Bs", "Packers": "Pk", "Lions": "Ln", "Vikings": "Vk",
        "Falcons": "Fc", "Panthers": "Ph", "Saints": "St", "Buccaneers": "Bc",
        "Cardinals": "Cd", "Rams": "Rm", "49ers": "49", "Seahawks": "Sh", "Ravens": "Rv",
        "Bengals": "Bg", "Browns": "Bn", "Steelers": "Sl", "Texans": "Tx", "Colts": "Ct",
        "Jaguars": "Jg", "Titans": "Tn", "Broncos": "Bc", "Chiefs": "Ch", "Raiders": "Rd",
        "Chargers": "Cr", "Bills": "Bl", "Dolphins": "Dp",
        # NBA
        "Celtics": "Cl", "Nets": "Nt", "Knicks": "Kc", "76ers": "76", "Raptors": "Rp",
        "Bulls": "Bl", "Cavaliers": "Cv", "Pistons": "Ps", "Pacers": "Pc", "Bucks": "Bk",
        "Hawks": "Hw", "Hornets": "Hn", "Heat": "Ht", "Magic": "Mg", "Wizards": "Wz",
        "Nuggets": "Ng", "Timberwolves": "Tw", "Thunder": "Th", "Trailblazers": "Tb",
        "Jazz": "Jz", "Warriors": "Wa", "Clippers": "Cp", "Lakers": "Lk", "Suns": "Sn",
        "Kings": "Kg", "Mavericks": "Mv", "Rockets": "Rk", "Grizzlies": "Gz",
        "Pelicans": "Pl", "Spurs": "Sp",
        # MLB
        "Yankees": "Yk", "RedSox": "Rx", "BlueJays": "Bj", "Orioles": "Or", "Rays": "Ry",
        "WhiteSox": "Wx", "Guardians": "Gd", "Tigers": "Tg", "Royals": "Ry", "Twins": "Tn",
        "Astros": "As", "Angels": "An", "Athletics": "At", "Mariners": "Mn", "Rangers": "Rg",
        "Braves": "Bv", "Marlins": "Ml", "Mets": "Mt", "Phillies": "Ph", "Nationals": "Nl",
        "Cubs": "Cb", "Reds": "Rd", "Brewers": "Br", "Pirates": "Pt", "Cardinals": "Cd",
        "Diamondbacks": "Db", "Rockies": "Rk", "Dodgers": "Dg", "Padres": "Pd", "Giants": "Gt",
        # NHL
        "Bruins": "Bn", "Sabres": "Sb", "Hurricanes": "Hc", "BlueJackets": "Bj",
        "RedWings": "Rw", "Panthers": "Ph", "Canadiens": "Cn", "Devils": "Dv",
        "Islanders": "Is", "Rangers": "Rg", "Senators": "Sn", "Flyers": "Fy",
        "Penguins": "Pg", "Sharks": "Sk", "Blues": "Bl", "Lightning": "Lt",
        "MapleLeafs": "Ml", "Canucks": "Ck", "Capitals": "Cp", "Jets": "Jt",
        "Ducks": "Dk", "Coyotes": "Cy", "Flames": "Fm", "Oilers": "Ol", "Kings": "Kg",
        "Wild": "Wd", "Predators": "Pr", "Stars": "Sr", "Avalanche": "Av", "Blackhawks": "Bh"
    }
    
    # Generate username components
    animal_name = random.choice(list(animals.keys()))
    animal_abbrev = animals[animal_name]
    area_code = random.choice(area_codes)
    team_name = random.choice(list(sports_teams.keys()))
    team_abbrev = sports_teams[team_name]
    
    # Create base username: day (1-2) + animal (2) + area (3) + team (2) = 8-9 chars
    # Note: underscore prefix will be added, so we have 11 chars for content (12 total)
    base_username = f"{day}{animal_abbrev}{area_code}{team_abbrev}"
    username = f"_{base_username}"
    
    # Ensure uniqueness by appending a number if needed (max 12 chars total including underscore)
    # Base is 8-9 chars + underscore = 9-10 chars, so we have 2-3 chars available for counter
    counter = 1
    while User.objects.filter(username=username).exists():
        counter_str = str(counter)
        # Calculate how much space we have (12 total - 1 for underscore = 11 for content)
        base_content_len = len(base_username)
        available = 11 - base_content_len
        
        if available >= len(counter_str):
            # We have enough space for the counter
            username = f"_{base_username}{counter_str}"
        else:
            # Not enough space, truncate base to make room
            truncate_to = 11 - len(counter_str)
            truncated_base = base_username[:max(1, truncate_to)]
            username = f"_{truncated_base}{counter_str}"
        
        counter += 1
        
        # Safety check to prevent infinite loop
        if counter > 9999:
            # Fallback: use timestamp-based unique identifier
            import time
            timestamp_str = str(int(time.time()) % 10000000000)  # Last 10 digits
            # Ensure total length is 12 (1 underscore + up to 11 chars)
            if len(timestamp_str) > 11:
                timestamp_str = timestamp_str[:11]
            username = f"_{timestamp_str}"
            break
    
    # Final check: ensure username doesn't exceed 12 characters (including underscore)
    if len(username) > 12:
        username = username[:12]
    
    return username