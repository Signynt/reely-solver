import tmdbsimple as tmdb
from itertools import combinations
tmdb.API_KEY = ''

# --- Settings ---
STOP_ON_FIRST_CONNECTION = False
OUTPUT_FILE = "connections.txt"
# ----------------

# Clear the output file at the start of the run
with open(OUTPUT_FILE, "w") as f:
    f.write("Found Connections:\n")

search = tmdb.Search()
name1 = 'White Chicks'
year1 = 2004
response1 = search.movie(query=name1)

name2 = 'Ballerina'
year2 = 2025
response2 = search.movie(query=name2)

# Go through the serach results, and find the movie with the correct year
for result in response1['results']:
    if result['title'] == name1 and result['release_date'].startswith(str(year1)):
        movie1_id = result['id']
        break
else:
    raise ValueError(f"Movie '{name1}' not found for year {year1}")

for result in response2['results']:
    if result['title'] == name2 and result['release_date'].startswith(str(year2)):
        movie2_id = result['id']
        break
else:
    raise ValueError(f"Movie '{name2}' not found for year {year2}")

movie1 = tmdb.Movies(movie1_id)
movie2 = tmdb.Movies(movie2_id)

# Get the actors for the first movie
movie1_credits = movie1.credits()
actors1 = [actor['name'] for actor in movie1_credits['cast']]

# Get the actors for the second movie
movie2_credits = movie2.credits()
actors2 = [actor['name'] for actor in movie2_credits['cast']]

# Check if there is any actor in common
depth = 1
found_in_common = False

# Create two dictionaries, one for each starting movie's "family"
movies_actors1 = {name1: actors1}
movies_actors2 = {name2: actors2}

# Keep track of actors we've already searched for on each side
searched_actors1 = set()
searched_actors2 = set()

def reconstruct_path(movie_title, movies_actors_dict, start_name):
    """Reconstructs the path from a movie back to the starting movie."""
    path = []
    curr_movie = movie_title
    while curr_movie != start_name:
        _, source_actor, source_movie = movies_actors_dict[curr_movie]
        path.insert(0, f"'{source_actor}' -> '{curr_movie}'")
        curr_movie = source_movie
    return f"'{start_name}' -> " + " -> ".join(path)

def expand_and_check(movies_actors_to_expand, searched_actors, other_movies_actors, search_api, start_name_expand, start_name_other):
    """Expands a set of movies and checks for a connection after each addition."""
    connection_found_this_pass = False
    actors_to_search = set(actor for actors_list, _, _ in movies_actors_to_expand.values() for actor in actors_list) - searched_actors

    for actor_name in actors_to_search:
        if actor_name in searched_actors:
            continue
        searched_actors.add(actor_name)
        
        try:
            person_search = search_api.person(query=actor_name)
            if not person_search['results']:
                continue
            person_id = person_search['results'][0]['id']
            person_credits = tmdb.People(person_id).movie_credits()

            # Find which movie in our current set led us to this actor
            source_movie_title = None
            for movie, (actors, _, _) in movies_actors_to_expand.items():
                if actor_name in actors:
                    source_movie_title = movie
                    break
            
            if not source_movie_title: continue

            for movie_credit in person_credits['cast']:
                new_movie_title = movie_credit['title']
                
                if new_movie_title not in movies_actors_to_expand:
                    print(f"Adding movie: '{new_movie_title}' (via {actor_name} from '{source_movie_title}')")
                    movie_obj = tmdb.Movies(movie_credit['id'])
                    credits = movie_obj.credits()
                    new_movie_cast = [actor['name'] for actor in credits['cast']]
                    
                    # Store the new movie with its path information
                    movies_actors_to_expand[new_movie_title] = (new_movie_cast, actor_name, source_movie_title)

                    # Check for connection with the other set immediately
                    for other_movie_title, (other_movie_cast, _, _) in other_movies_actors.items():
                        common_actors = set(new_movie_cast).intersection(other_movie_cast)
                        if common_actors:
                            connection_found_this_pass = True
                            common_actor = common_actors.pop()
                            print("\n--- Connection Found! ---")
                            path1 = reconstruct_path(new_movie_title, movies_actors_to_expand, start_name_expand)
                            path2 = reconstruct_path(other_movie_title, other_movies_actors, start_name_other)
                            
                            # Reverse the second path to flow correctly
                            reversed_path2_parts = path2.split(' -> ')
                            reversed_path2 = " -> ".join(reversed(reversed_path2_parts))

                            full_path = f"{path1} -> '{common_actor}' -> {reversed_path2}"
                            print("Full connection path:")
                            print(full_path)

                            # Write to output file
                            with open(OUTPUT_FILE, "a") as f:
                                f.write(full_path + "\n")
                            
                            if STOP_ON_FIRST_CONNECTION:
                                return True # Signal to stop the entire search
        except Exception as e:
            print(f"Could not process actor {actor_name}: {e}")
    
    return connection_found_this_pass

# Change the structure to store path information: {movie_title: (actors, source_actor, source_movie)}
movies_actors1 = {name1: (actors1, None, None)}
movies_actors2 = {name2: (actors2, None, None)}

any_connection_found = False
# Loop until a connection is found or search space is exhausted
while True:
    depth += 1
    print(f"\n--- Expanding search to depth {depth} ---")

    if any_connection_found and not STOP_ON_FIRST_CONNECTION:
        print("\nConnections found at the previous depth. Stopping search.")
        break

    # Expand from name1's side and check for connections
    print(f"\nExpanding from '{name1}'s side...")
    if expand_and_check(movies_actors1, searched_actors1, movies_actors2, search, name1, name2):
        any_connection_found = True
        if STOP_ON_FIRST_CONNECTION:
            break

    # If no connection yet (or we want all connections at this depth), expand from name2's side
    print(f"\nExpanding from '{name2}'s side...")
    if expand_and_check(movies_actors2, searched_actors2, movies_actors1, search, name2, name1):
        any_connection_found = True
        if STOP_ON_FIRST_CONNECTION:
            break

    # Check if we are stuck
    actors_to_search1 = set(actor for actors_list, _, _ in movies_actors1.values() for actor in actors_list) - searched_actors1
    actors_to_search2 = set(actor for actors_list, _, _ in movies_actors2.values() for actor in actors_list) - searched_actors2
    if not actors_to_search1 and not actors_to_search2:
        print("\nCould not find any new movies to expand the search. Stopping.")
        break

if not any_connection_found:
    print("\nSearch complete. No connections were found.")
else:
    print("\nSearch complete. Check connections.txt for any found paths.")