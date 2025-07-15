import tmdbsimple as tmdb
import csv
tmdb.API_KEY = ''

# --- Settings ---
STOP_ON_FIRST_CONNECTION = False
OUTPUT_FILE = "connections.csv"
# ----------------

# This will store the minimum number of movies found in a connection.
min_connection_movies = float('inf')

# Clear the output file and write the CSV header
with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Connection", "Average Popularity"])

search = tmdb.Search()
name1 = 'Shazam!'
year1 = 2019
response1 = search.movie(query=name1)

name2 = 'Spider-Man'
year2 = 2002
response2 = search.movie(query=name2)

# Go through the search results, and find the movie with the correct year
for result in response1['results']:
    if result['title'] == name1 and result['release_date'].startswith(str(year1)):
        movie1_id = result['id']
        movie1_popularity = result['popularity']
        break
else:
    raise ValueError(f"Movie '{name1}' not found for year {year1}")

for result in response2['results']:
    if result['title'] == name2 and result['release_date'].startswith(str(year2)):
        movie2_id = result['id']
        movie2_popularity = result['popularity']
        break
else:
    raise ValueError(f"Movie '{name2}' not found for year {year2}")

movie1 = tmdb.Movies(movie1_id)
movie2 = tmdb.Movies(movie2_id)

# Get the actors and their popularities for the first movie
movie1_credits = movie1.credits()
actors1 = {actor['name']: actor['popularity'] for actor in movie1_credits['cast']}

# Get the actors and their popularities for the second movie
movie2_credits = movie2.credits()
actors2 = {actor['name']: actor['popularity'] for actor in movie2_credits['cast']}

# Check if there is any actor in common
depth = 1
found_in_common = False

# Keep track of actors we've already searched for on each side
searched_actors1 = set()
searched_actors2 = set()

def reconstruct_path(movie_title, movies_actors_dict, start_name):
    """Reconstructs the path from a movie back to the starting movie, collecting popularities."""
    path_str_parts = []
    path_items = [] # List to store (type, name, popularity) tuples
    
    curr_movie_title = movie_title
    while curr_movie_title != start_name:
        movie_info = movies_actors_dict[curr_movie_title]
        movie_popularity = movie_info['popularity']
        source_actor = movie_info['source_actor']
        source_actor_popularity = movie_info['source_actor_popularity']
        source_movie = movie_info['source_movie']

        path_str_parts.insert(0, f"'{source_actor}' -> '{curr_movie_title}'")
        path_items.insert(0, ('Movie', curr_movie_title, movie_popularity))
        path_items.insert(0, ('Actor', source_actor, source_actor_popularity))
        
        curr_movie_title = source_movie

    # Add the starting movie
    start_movie_info = movies_actors_dict[start_name]
    path_items.insert(0, ('Movie', start_name, start_movie_info['popularity']))
    
    full_path_str = f"'{start_name}' -> " + " -> ".join(path_str_parts)
    return full_path_str, path_items

def expand_and_check(movies_actors_to_expand, searched_actors, other_movies_actors, search_api, start_name_expand, start_name_other):
    """Expands a set of movies and checks for a connection after each addition."""
    global min_connection_movies
    connection_found_this_pass = False
    
    # Create a flat set of all actors from the movies to be expanded
    actors_to_search = set()
    for movie_data in movies_actors_to_expand.values():
        actors_to_search.update(movie_data['actors'].keys())
    actors_to_search -= searched_actors

    for actor_name in actors_to_search:
        if actor_name in searched_actors:
            continue
        searched_actors.add(actor_name)
        
        try:
            person_search = search_api.person(query=actor_name)
            if not person_search['results']:
                continue
            
            person_info = person_search['results'][0]
            person_id = person_info['id']
            actor_popularity = person_info['popularity']
            person_credits = tmdb.People(person_id).movie_credits()

            # Find which movie in our current set led us to this actor
            source_movie_title = None
            for title, data in movies_actors_to_expand.items():
                if actor_name in data['actors']:
                    source_movie_title = title
                    break
            
            if not source_movie_title: continue

            for movie_credit in person_credits['cast']:
                new_movie_title = movie_credit['title']
                
                # Prevent cycles by not adding a movie that's already been seen on either side
                if new_movie_title not in movies_actors_to_expand and new_movie_title not in other_movies_actors:
                    print(f"Adding movie: '{new_movie_title}' (via {actor_name} from '{source_movie_title}')")
                    movie_obj = tmdb.Movies(movie_credit['id'])
                    credits = movie_obj.credits()
                    new_movie_cast = {actor['name']: actor['popularity'] for actor in credits['cast']}
                    
                    # Store the new movie with its path information and popularity
                    movies_actors_to_expand[new_movie_title] = {
                        'actors': new_movie_cast,
                        'source_actor': actor_name,
                        'source_actor_popularity': actor_popularity,
                        'source_movie': source_movie_title,
                        'popularity': movie_credit.get('popularity', 0)
                    }

                    # Check for connection with the other set immediately
                    for other_movie_title, other_movie_data in other_movies_actors.items():
                        common_actor_names = set(new_movie_cast.keys()).intersection(other_movie_data['actors'].keys())
                        
                        if common_actor_names:
                            path1_str, path1_items = reconstruct_path(new_movie_title, movies_actors_to_expand, start_name_expand)
                            path2_str, path2_items = reconstruct_path(other_movie_title, other_movies_actors, start_name_other)
                            
                            # Calculate the number of movies in this connection
                            num_movies = sum(1 for item in path1_items if item[0] == 'Movie') + \
                                         sum(1 for item in path2_items if item[0] == 'Movie')

                            # If this connection is longer than the shortest one found, skip it.
                            if num_movies > min_connection_movies:
                                print(f"\nFound a longer connection ({num_movies} movies). Discarding.")
                                continue

                            connection_found_this_pass = True
                            common_actor_name = common_actor_names.pop()
                            common_actor_popularity = new_movie_cast.get(common_actor_name, 0)

                            print("\n--- Connection Found! ---")
                            
                            # If this is a new shortest path, update the minimum and clear the output file.
                            if num_movies < min_connection_movies:
                                print(f"New shortest connection found: {num_movies} movies. Clearing previous results.")
                                min_connection_movies = num_movies
                                with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
                                    writer = csv.writer(f)
                                    writer.writerow(["Connection", "Average Popularity"])

                            # Reverse the second path string for correct flow
                            reversed_path2_parts = path2_str.split(' -> ')
                            reversed_path2_str = " -> ".join(reversed(reversed_path2_parts))

                            full_path_str = f"{path1_str} -> '{common_actor_name}' -> {reversed_path2_str}"
                            print("Full connection path:")
                            print(full_path_str)

                            # Combine path items and calculate average popularity
                            all_path_items = path1_items + [('Actor', common_actor_name, common_actor_popularity)] + list(reversed(path2_items))
                            
                            total_popularity = sum(item[2] for item in all_path_items)
                            average_popularity = total_popularity / len(all_path_items) if all_path_items else 0
                            print(f"Average Popularity Score: {average_popularity:.2f}")

                            # Write to output file
                            with open(OUTPUT_FILE, "a", newline="", encoding="utf-8") as f:
                                writer = csv.writer(f)
                                writer.writerow([full_path_str, f"{average_popularity:.4f}"])
                            
                            if STOP_ON_FIRST_CONNECTION:
                                return True # Signal to stop the entire search
        except Exception as e:
            print(f"Could not process actor {actor_name}: {e}")
    
    return connection_found_this_pass

# New data structure: {movie_title: {'actors': {name: pop}, 'source_actor': str, 'source_actor_popularity': float, 'source_movie': str, 'popularity': float}}
movies_actors1 = {name1: {'actors': actors1, 'source_actor': None, 'source_actor_popularity': None, 'source_movie': None, 'popularity': movie1_popularity}}
movies_actors2 = {name2: {'actors': actors2, 'source_actor': None, 'source_actor_popularity': None, 'source_movie': None, 'popularity': movie2_popularity}}

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
    actors_to_search1 = set(actor for data in movies_actors1.values() for actor in data['actors']) - searched_actors1
    actors_to_search2 = set(actor for data in movies_actors2.values() for actor in data['actors']) - searched_actors2
    if not actors_to_search1 and not actors_to_search2:
        print("\nCould not find any new movies to expand the search. Stopping.")
        break

if not any_connection_found:
    print("\nSearch complete. No connections were found.")
else:
    print(f"\nSearch complete. Check {OUTPUT_FILE} for any found paths.")