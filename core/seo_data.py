from django.utils.text import slugify

AHMEDABAD_AREAS = [
    "Satellite", "Vastrapur", "Bodakdev", "Thaltej", "SG Highway", "Prahlad Nagar",
    "Navrangpura", "Ellisbridge", "Paldi", "Vasna", "Maninagar", "Isanpur", "Bhadaj",
    "Ghatlodia", "Naranpura", "Ranip", "Chandkheda", "Motera", "Sabarmati",
    "Gota", "Vaishnodevi", "Chandlodia", "Vejalpur", "Jodhpur", "Ambawadi", "Shahibaug",
    "Naroda", "Nikol", "Vastral", "Bapunagar", "Odhav", "Kubernagar",
    "Rakhial", "Amraiwadi", "Gomtipur", "Khokhra", "Kankaria", "Danilimda",
    "Vatva", "Lambha", "Narol", "Sarkhej", "Juhapura", "Makarba",
    "Ghuma", "South Bopal", "Bopal", "Shela", "Shilaj", "Science City", "Science Park",
    "Chharodi", "Nava Vadaj", "Vadaj", "Usmanpura", "Memnagar", "Gulbai Tekra",
    "Panjrapole", "C.G. Road", "Law Garden", "Navjivan", "Income Tax", "Stadium",
    "Nehru Nagar", "Judges Bungalow Road", "Iscon", "Anand Nagar", "Manekbaug",
    "Jivraj Park", "Vishala", "Nirnaynagar", "Chenpur", "Sughad", "Zundal",
    "Gandhinagar Road", "Adalaj", "Koba", "Randesan", "Kudasan", "New CG Road",
    "Bhat", "Sarangpur", "Kalupur", "Raikhad", "Dariapur", "Jamalpur",
    "Khadia", "Shahpur", "Dudheshwar", "Saraspur", "Rajpur", "Meghaninagar",
]

BHK_OPTIONS = ["1", "2", "3", "4", "5"]


def get_area_by_slug(location_slug):
    """URL slug (e.g. 'sg-highway') se actual area name (e.g. 'SG Highway') dhoondta hai."""
    for area in AHMEDABAD_AREAS:
        if slugify(area) == location_slug:
            return area
    return None


def get_area_slug(area_name):
    return slugify(area_name)