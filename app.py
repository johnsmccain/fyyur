#----------------------------------------------------------------------------#
# Imports
#----------------------------------------------------------------------------#

import json
import dateutil.parser
import babel
from flask import Flask, render_template, request, Response, flash, redirect, url_for, abort, jsonify
from flask_moment import Moment
from flask_sqlalchemy import SQLAlchemy
import logging
from logging import Formatter, FileHandler
#from flask_wtf import FlaskForm  (not used here but in forms.py)
from forms import *
from flask_migrate import Migrate

from datetime import datetime
import re
from operator import itemgetter # for sorting lists of tuples

#----------------------------------------------------------------------------#
# App Config.
#----------------------------------------------------------------------------#

app = Flask(__name__)
moment = Moment(app)
app.config.from_object('config')
db = SQLAlchemy(app)

# connect to a local postgresql database
migrate = Migrate(app, db)
from models import *
#----------------------------------------------------------------------------#
# Models.
#----------------------------------------------------------------------------#

def format_datetime(value, format='medium'):
    date = dateutil.parser.parse(value)
    if format == 'full':
        format = "EEEE MMMM, d, y 'at' h:mma"
    elif format == 'medium':
        format = "EE MM, dd, y h:mma"
    return babel.dates.format_datetime(date, format)


app.jinja_env.filters['datetime'] = format_datetime

#----------------------------------------------------------------------------#
# Controllers.
#----------------------------------------------------------------------------#

@app.route('/')
def index():
    return render_template('pages/home.html')


#  Venues
#  ----------------------------------------------------------------

@app.route('/venues')
def venues():
    venues = Venue.query.all()

    data = []   # A list of dictionaries, where city, state, and venues are dictionary keys

    cities_states = set()
    for venue in venues:
        cities_states.add( (venue.city, venue.state) )  # Add tuple
    
    cities_states = list(cities_states)
    cities_states.sort(key=itemgetter(1,0))     # Sorts on second column first (state), then by city.

    now = datetime.now()    # Don't get this over and over in a loop!

    for loc in cities_states:
        venues_list = []
        for venue in venues:
            if (venue.city == loc[0]) and (venue.state == loc[1]):

                venue_shows = Show.query.filter_by(venue_id=venue.id).all()
                num_upcoming = 0
                for show in venue_shows:
                    if show.start_time > now:
                        num_upcoming += 1

                venues_list.append({
                    "id": venue.id,
                    "name": venue.name,
                    "num_upcoming_shows": num_upcoming
                })

        data.append({
            "city": loc[0],
            "state": loc[1],
            "venues": venues_list
        })


    return render_template('pages/venues.html', areas=data)


@app.route('/venues/search', methods=['POST'])
def search_venues():
    search_term = request.form.get('search_term', '').strip()

    venues = Venue.query.filter(Venue.name.ilike('%' + search_term + '%')).all()   # Wildcards search before and after
    venue_list = []
    now = datetime.now()
    for venue in venues:
        venue_shows = Show.query.filter_by(venue_id=venue.id).all()
        num_upcoming = 0
        for show in venue_shows:
            if show.start_time > now:
                num_upcoming += 1

        venue_list.append({
            "id": venue.id,
            "name": venue.name,
            "num_upcoming_shows": num_upcoming  # FYI, template does nothing with this
        })

    response = {
        "count": len(venues),
        "data": venue_list
    }
 
    return render_template('pages/search_venues.html', results=response, search_term=search_term)


@app.route('/venues/<int:venue_id>')
def show_venue(venue_id):
  
    venue = Venue.query.get(venue_id)   # Returns object by primary key, or None
    print(venue)
    if not venue:
      
        return redirect(url_for('index'))
    else:
       
        genres = [ genre.name for genre in venue.genres ]
        
        past_shows = []
        past_shows_count = 0
        upcoming_shows = []
        upcoming_shows_count = 0
        now = datetime.now()
        for show in venue.shows:
            if show.start_time > now:
                upcoming_shows_count += 1
                upcoming_shows.append({
                    "artist_id": show.artist_id,
                    "artist_name": show.artist.name,
                    "artist_image_link": show.artist.image_link,
                    "start_time": format_datetime(str(show.start_time))
                })
            if show.start_time < now:
                past_shows_count += 1
                past_shows.append({
                    "artist_id": show.artist_id,
                    "artist_name": show.artist.name,
                    "artist_image_link": show.artist.image_link,
                    "start_time": format_datetime(str(show.start_time))
                })

        data = {
            "id": venue_id,
            "name": venue.name,
            "genres": genres,
            "address": venue.address,
            "city": venue.city,
            "state": venue.state,
            "phone": (venue.phone[:3] + '-' + venue.phone[3:6] + '-' + venue.phone[6:]),
            "website": venue.website,
            "facebook_link": venue.facebook_link,
            "seeking_talent": venue.seeking_talent,
            "seeking_description": venue.seeking_description,
            "image_link": venue.image_link,
            "past_shows": past_shows,
            "past_shows_count": past_shows_count,
            "upcoming_shows": upcoming_shows,
            "upcoming_shows_count": upcoming_shows_count
        }
            
    return render_template('pages/show_venue.html', venue=data)

#  Create Venue
#  ----------------------------------------------------------------

@app.route('/venues/create', methods=['GET'])
def create_venue_form():
    form = VenueForm()
    return render_template('forms/new_venue.html', form=form)


@app.route('/venues/create', methods=['POST'])
def create_venue_submission():
    form = VenueForm()

    name = form.name.data.strip()
    city = form.city.data.strip()
    state = form.state.data
    address = form.address.data.strip()
    phone = form.phone.data
    
    phone = re.sub('\D', '', phone) # e.g. (819) 392-1234 --> 8193921234
    genres = form.genres.data                   # ['Alternative', 'Classical', 'Country']
    seeking_talent = True if form.seeking_talent.data == 'Yes' else False
    seeking_description = form.seeking_description.data.strip()
    image_link = form.image_link.data.strip()
    website = form.website.data.strip()
    facebook_link = form.facebook_link.data.strip()
    
    
    if not form.validate():
        flash( form.errors )
        return redirect(url_for('create_venue_submission'))

    else:
        error_in_insert = False

        # Insert form data into DB
        try:
                # creates the new venue with all fields but not genre yet
            new_venue = Venue(name=name, city=city, state=state, address=address, phone=phone, \
                seeking_talent=seeking_talent, seeking_description=seeking_description, image_link=image_link, \
                website=website, facebook_link=facebook_link)
            # genres can't take a list of strings, it needs to be assigned to db objects
            # genres from the form is like: ['Alternative', 'Classical', 'Country']
            for genre in genres:
                # fetch_genre = session.query(Genre).filter_by(name=genre).one_or_none()  # Throws an exception if more than one returned, returns None if none
                fetch_genre = Genre.query.filter_by(name=genre).one_or_none()  # Throws an exception if more than one returned, returns None if none
                if fetch_genre:
                    # if found a genre, append it to the list
                    new_venue.genres.append(fetch_genre)

                else:
                    # fetch_genre was None. It's not created yet, so create it
                    new_genre = Genre(name=genre)
                    db.session.add(new_genre)
                    new_venue.genres.append(new_genre)  # Create a new Genre item and append it

            db.session.add(new_venue)
            db.session.commit()
        except Exception as e:
            error_in_insert = True
            print(f'Exception "{e}" in create_venue_submission()')
            db.session.rollback()
        finally:
            db.session.close()

        if not error_in_insert:
            # on successful db insert, flash success
            flash('Venue ' + request.form['name'] + ' was successfully listed!')
            return redirect(url_for('index'))
        else:
            flash('An error occurred. Venue ' + name + ' could not be listed.')
            print("Error in create_venue_submission()")
            # return redirect(url_for('create_venue_submission'))
            abort(500)


@app.route('/venues/<venue_id>/delete', methods=['GET'])
def delete_venue(venue_id):
    venue = Venue.query.get(venue_id)
    if not venue:
        return redirect(url_for('index'))
    else:
        error_on_delete = False
        venue_name = venue.name
        try:
            db.session.delete(venue)
            db.session.commit()
        except:
            error_on_delete = True
            db.session.rollback()
        finally:
            db.session.close()
        if error_on_delete:
            flash(f'An error occurred deleting venue {venue_name}.')
            print("Error in delete_venue()")
            abort(500)
        else:
           
            return jsonify({
                'deleted': True,
                'url': url_for('venues')
            })


#  Artists
#  ----------------------------------------------------------------
@app.route('/artists')
def artists():
    artists = Artist.query.order_by(Artist.name).all()  # Sort alphabetically

    data = []
    for artist in artists:
        data.append({
            "id": artist.id,
            "name": artist.name
        })

  
    return render_template('pages/artists.html', artists=data)


@app.route('/artists/search', methods=['POST'])
def search_artists():
  
    search_term = request.form.get('search_term', '').strip()

  
    artists = Artist.query.filter(Artist.name.ilike('%' + search_term + '%')).all()   # Wildcards search before and after
  
    artist_list = []
    now = datetime.now()
    for artist in artists:
        artist_shows = Show.query.filter_by(artist_id=artist.id).all()
        num_upcoming = 0
        for show in artist_shows:
            if show.start_time > now:
                num_upcoming += 1

        artist_list.append({
            "id": artist.id,
            "name": artist.name,
            "num_upcoming_shows": num_upcoming  # FYI, template does nothing with this
        })

    response = {
        "count": len(artists),
        "data": artist_list
    }

    return render_template('pages/search_artists.html', results=response, search_term=request.form.get('search_term', ''))


@app.route('/artists/<int:artist_id>')
def show_artist(artist_id):
  
    artist = Artist.query.get(artist_id)   # Returns object by primary key, or None
    print(artist)
    if not artist:
  
        return redirect(url_for('index'))
    else:
  
        genres = [ genre.name for genre in artist.genres ]
        
  
        past_shows = []
        past_shows_count = 0
        upcoming_shows = []
        upcoming_shows_count = 0
        now = datetime.now()
        for show in artist.shows:
            if show.start_time > now:
                upcoming_shows_count += 1
                upcoming_shows.append({
                    "venue_id": show.venue_id,
                    "venue_name": show.venue.name,
                    "venue_image_link": show.venue.image_link,
                    "start_time": format_datetime(str(show.start_time))
                })
            if show.start_time < now:
                past_shows_count += 1
                past_shows.append({
                    "venue_id": show.venue_id,
                    "venue_name": show.venue.name,
                    "venue_image_link": show.venue.image_link,
                    "start_time": format_datetime(str(show.start_time))
                })

        data = {
            "id": artist_id,
            "name": artist.name,
            "genres": genres,
            "city": artist.city,
            "state": artist.state,  
            "phone": (artist.phone[:3] + '-' + artist.phone[3:6] + '-' + artist.phone[6:]),
            "website": artist.website,
            "facebook_link": artist.facebook_link,
            "seeking_venue": artist.seeking_venue,
            "seeking_description": artist.seeking_description,
            "image_link": artist.image_link,
            "past_shows": past_shows,
            "past_shows_count": past_shows_count,
            "upcoming_shows": upcoming_shows,
            "upcoming_shows_count": upcoming_shows_count
        }

   
    return render_template('pages/show_artist.html', artist=data)

#  Update
#  ----------------------------------------------------------------
@app.route('/artists/<int:artist_id>/edit', methods=['GET'])
def edit_artist(artist_id):
   
    artist = Artist.query.get(artist_id)  # Returns object based on primary key, or None.  Guessing get is faster than filter_by
    if not artist:
        return redirect(url_for('index'))
    else:
        form = ArtistForm(obj=artist)

    genres = [ genre.name for genre in artist.genres ]
    
    artist = {
        "id": artist_id,
        "name": artist.name,
        "genres": genres,
        "city": artist.city,
        "state": artist.state,
        "phone": (artist.phone[:3] + '-' + artist.phone[3:6] + '-' + artist.phone[6:]),
        "website": artist.website,
        "facebook_link": artist.facebook_link,
        "seeking_venue": artist.seeking_venue,
        "seeking_description": artist.seeking_description,
        "image_link": artist.image_link
    }
    return render_template('forms/edit_artist.html', form=form, artist=artist)


@app.route('/artists/<int:artist_id>/edit', methods=['POST'])
def edit_artist_submission(artist_id):
    form = ArtistForm()

    name = form.name.data.strip()
    city = form.city.data.strip()
    state = form.state.data
    phone = form.phone.data
    phone = re.sub('\D', '', phone) # e.g. (819) 392-1234 --> 8193921234
    genres = form.genres.data                   # ['Alternative', 'Classical', 'Country']
    seeking_venue = True if form.seeking_venue.data == 'Yes' else False
    seeking_description = form.seeking_description.data.strip()
    image_link = form.image_link.data.strip()
    website = form.website.data.strip()
    facebook_link = form.facebook_link.data.strip()

    if not form.validate():
        flash( form.errors )
        return redirect(url_for('edit_artist_submission', artist_id=artist_id))

    else:
        error_in_update = False

        try:
            artist = Artist.query.get(artist_id)
            artist.name = name
            artist.city = city
            artist.state = state
            artist.phone = phone
            artist.seeking_venue = seeking_venue
            artist.seeking_description = seeking_description
            artist.image_link = image_link
            artist.website = website
            artist.facebook_link = facebook_link

            artist.genres = []
            
            for genre in genres:
                fetch_genre = Genre.query.filter_by(name=genre).one_or_none()  # Throws an exception if more than one returned, returns None if none
                if fetch_genre:
                    artist.genres.append(fetch_genre)

                else:
                    new_genre = Genre(name=genre)
                    db.session.add(new_genre)
                    artist.genres.append(new_genre)  # Create a new Genre item and append it

            db.session.commit()
        except Exception as e:
            error_in_update = True
            print(f'Exception "{e}" in edit_artist_submission()')
            db.session.rollback()
        finally:
            db.session.close()

        if not error_in_update:
            # on successful db update, flash success
            flash('Artist ' + request.form['name'] + ' was successfully updated!')
            return redirect(url_for('show_artist', artist_id=artist_id))
        else:
            flash('An error occurred. Artist ' + name + ' could not be updated.')
            print("Error in edit_artist_submission()")
            abort(500)


@app.route('/venues/<int:venue_id>/edit', methods=['GET'])
def edit_venue(venue_id):
    venue = Venue.query.get(venue_id)  # Returns object based on primary key, or None.  Guessing get is faster than filter_by
    if not venue:
        # User typed in a URL that doesn't exist, redirect home
        return redirect(url_for('index'))
    else:
        # Otherwise, valid venue.  We can prepopulate the form with existing data like this:
        form = VenueForm(obj=venue)

    genres = [ genre.name for genre in venue.genres ]
    
    venue = {
        "id": venue_id,
        "name": venue.name,
        "genres": genres,
        "address": venue.address,
        "city": venue.city,
        "state": venue.state,
        # Put the dashes back into phone number
        "phone": (venue.phone[:3] + '-' + venue.phone[3:6] + '-' + venue.phone[6:]),
        "website": venue.website,
        "facebook_link": venue.facebook_link,
        "seeking_talent": venue.seeking_talent,
        "seeking_description": venue.seeking_description,
        "image_link": venue.image_link
    }
    return render_template('forms/edit_venue.html', form=form, venue=venue)


@app.route('/venues/<int:venue_id>/edit', methods=['POST'])
def edit_venue_submission(venue_id):
    form = VenueForm()

    name = form.name.data.strip()
    city = form.city.data.strip()
    state = form.state.data
    address = form.address.data.strip()
    phone = form.phone.data
    # Normalize DB.  Strip anything from phone that isn't a number
    phone = re.sub('\D', '', phone) # e.g. (819) 392-1234 --> 8193921234
    genres = form.genres.data                   # ['Alternative', 'Classical', 'Country']
    seeking_talent = True if form.seeking_talent.data == 'Yes' else False
    seeking_description = form.seeking_description.data.strip()
    image_link = form.image_link.data.strip()
    website = form.website.data.strip()
    facebook_link = form.facebook_link.data.strip()
    
    # Redirect back to form if errors in form validation
    if not form.validate():
        flash( form.errors )
        return redirect(url_for('edit_venue_submission', venue_id=venue_id))

    else:
        error_in_update = False

        # Insert form data into DB
        try:
            # First get the existing venue object
            venue = Venue.query.get(venue_id)
            # venue = Venue.query.filter_by(id=venue_id).one_or_none()

            # Update fields
            venue.name = name
            venue.city = city
            venue.state = state
            venue.address = address
            venue.phone = phone

            venue.seeking_talent = seeking_talent
            venue.seeking_description = seeking_description
            venue.image_link = image_link
            venue.website = website
            venue.facebook_link = facebook_link

            venue.genres = []
            for genre in genres:
                fetch_genre = Genre.query.filter_by(name=genre).one_or_none()  # Throws an exception if more than one returned, returns None if none
                if fetch_genre:
                    # if found a genre, append it to the list
                    venue.genres.append(fetch_genre)

                else:
                    # fetch_genre was None. It's not created yet, so create it
                    new_genre = Genre(name=genre)
                    db.session.add(new_genre)
                    venue.genres.append(new_genre)  # Create a new Genre item and append it

            # Attempt to save everything
            db.session.commit()
        except Exception as e:
            error_in_update = True
            print(f'Exception "{e}" in edit_venue_submission()')
            db.session.rollback()
        finally:
            db.session.close()

        if not error_in_update:
            # on successful db update, flash success
            flash('Venue ' + request.form['name'] + ' was successfully updated!')
            return redirect(url_for('show_venue', venue_id=venue_id))
        else:
            flash('An error occurred. Venue ' + name + ' could not be updated.')
            print("Error in edit_venue_submission()")
            abort(500)


#  Create Artist
#  ----------------------------------------------------------------
@app.route('/artists/create', methods=['GET'])
def create_artist_form():
    form = ArtistForm()
    return render_template('forms/new_artist.html', form=form)


@app.route('/artists/create', methods=['POST'])
def create_artist_submission():

    # Much of this code is similar to create_venue view
    form = ArtistForm()

    name = form.name.data.strip()
    city = form.city.data.strip()
    state = form.state.data
    # address = form.address.data.strip()
    phone = form.phone.data
    # Normalize DB.  Strip anything from phone that isn't a number
    phone = re.sub('\D', '', phone) # e.g. (819) 392-1234 --> 8193921234
    genres = form.genres.data                   # ['Alternative', 'Classical', 'Country']
    seeking_venue = True if form.seeking_venue.data == 'Yes' else False
    seeking_description = form.seeking_description.data.strip()
    image_link = form.image_link.data.strip()
    website = form.website.data.strip()
    facebook_link = form.facebook_link.data.strip()
    
    # Redirect back to form if errors in form validation
    if not form.validate():
        flash( form.errors )
        return redirect(url_for('create_artist_submission'))

    else:
        error_in_insert = False

        # Insert form data into DB
        try:
            # creates the new artist with all fields but not genre yet
            new_artist = Artist(name=name, city=city, state=state, phone=phone, \
                seeking_venue=seeking_venue, seeking_description=seeking_description, image_link=image_link, \
                website=website, facebook_link=facebook_link)
            for genre in genres:
                # fetch_genre = session.query(Genre).filter_by(name=genre).one_or_none()  # Throws an exception if more than one returned, returns None if none
                fetch_genre = Genre.query.filter_by(name=genre).one_or_none()  # Throws an exception if more than one returned, returns None if none
                if fetch_genre:
                    # if found a genre, append it to the list
                    new_artist.genres.append(fetch_genre)

                else:
                    # fetch_genre was None. It's not created yet, so create it
                    new_genre = Genre(name=genre)
                    db.session.add(new_genre)
                    new_artist.genres.append(new_genre)  # Create a new Genre item and append it

            db.session.add(new_artist)
            db.session.commit()
        except Exception as e:
            error_in_insert = True
            print(f'Exception "{e}" in create_artist_submission()')
            db.session.rollback()
        finally:
            db.session.close()

        if not error_in_insert:
            # on successful db insert, flash success
            flash('Artist ' + request.form['name'] + ' was successfully listed!')
            return redirect(url_for('index'))
        else:
            flash('An error occurred. Artist ' + name + ' could not be listed.')
            print("Error in create_artist_submission()")
            abort(500)


@app.route('/artists/<artist_id>/delete', methods=['GET'])
def delete_artist(artist_id):
    # Deletes a artist based on AJAX call from the artist page
    artist = Artist.query.get(artist_id)
    if not artist:
        # User somehow faked this call, redirect home
        return redirect(url_for('index'))
    else:
        error_on_delete = False
        # Need to hang on to artist name since will be lost after delete
        artist_name = artist.name
        try:
            db.session.delete(artist)
            db.session.commit()
        except:
            error_on_delete = True
            db.session.rollback()
        finally:
            db.session.close()
        if error_on_delete:
            flash(f'An error occurred deleting artist {artist_name}.')
            print("Error in delete_artist()")
            abort(500)
        else:
            return jsonify({
                'deleted': True,
                'url': url_for('artists')
            })


#  Shows
#  ----------------------------------------------------------------

@app.route('/shows')
def shows():
    # displays list of shows at /shows
    data = []
    shows = Show.query.all()
    
    for show in shows:
        # Can reference show.artist, show.venue
        data.append({
            "venue_id": show.venue.id,
            "venue_name": show.venue.name,
            "artist_id": show.artist.id,
            "artist_name": show.artist.name,
            "artist_image_link": show.artist.image_link,
            "start_time": format_datetime(str(show.start_time))
        })

    return render_template('pages/shows.html', shows=data)


@app.route('/shows/create', methods=['GET'])
def create_shows():
    # renders form. do not touch. (--> nyah nyah!  I touched it!)
    form = ShowForm()
    return render_template('forms/new_show.html', form=form)


@app.route('/shows/create', methods=['POST'])
def create_show_submission():
    # called to create new shows in the db, upon submitting new show listing form
    form = ShowForm()

    artist_id = form.artist_id.data.strip()
    venue_id = form.venue_id.data.strip()
    start_time = form.start_time.data

    error_in_insert = False
    
    try:
        new_show = Show(start_time=start_time, artist_id=artist_id, venue_id=venue_id)
        db.session.add(new_show)
        db.session.commit()
    except:
        error_in_insert = True
        print(f'Exception "{e}" in create_show_submission()')
        db.session.rollback()
    finally:
        db.session.close()

    if error_in_insert:
        flash(f'An error occurred.  Show could not be listed.')
        print("Error in create_show_submission()")
    else:
        flash('Show was successfully listed!')
    
    return render_template('pages/home.html')


@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def server_error(error):
    return render_template('errors/500.html'), 500


if not app.debug:
    file_handler = FileHandler('error.log')
    file_handler.setFormatter(
        Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
    )
    app.logger.setLevel(logging.INFO)
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.info('errors')

#----------------------------------------------------------------------------#
# Launch.
#----------------------------------------------------------------------------#

# Default port:
if __name__ == '__main__':
    app.run()

# Or specify port manually:
'''
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
'''
